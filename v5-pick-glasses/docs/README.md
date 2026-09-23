# Walkthrough

Six documents, one per stage of a run, in the order the arm does them. Read
[`../problem-statement.md`](../problem-statement.md) first if you have not.
These six explain *how* the task is done. That one explains what the task is
and why it is worth doing, which is the part that makes the rest make sense.

## The arc

The six stages are not a list of features. Each one exists because the stage
before it deliberately stopped short, and following that thread is the fastest
way to understand the design.

The arm begins knowing nothing about the table.

**Step 1** finds the glasses from above. It produces a position and a rough
width for each, and nothing else, because from overhead a tall glass and a
short one look the same. It can find them at all because the glasses here are
opaque. That is an assumption the [problem
statement](../problem-statement.md) sets out, not a fact about glassware, and
it is the one that would have to go first to make this a kitchen.

The shape that step 1 could not see is what **step 2** goes round to the side
to measure. One picture becomes a width at every height up the glass.

That profile is a description of the shape. So **step 3** can name the kind of
glass with arithmetic instead of a trained model. Naming it is worth doing for
one reason: the kind selects which rule applies.

**Step 4** applies that rule. It turns "hold the narrowest part below the bowl"
into a height and a finger gap for this glass.

**Step 5** answers the one question none of the looking could — how hard to
press. It weighs the glass in the air, because wall thickness is invisible and
weight does not follow from size.

**Step 6** turns the glass over and stands it down. It feels for the rack
rather than driving to a height, because by then two measured numbers have been
added together and both carry error.

Read end to end, the thread is simple. Each step hands on the least it can.
Anything a step cannot know honestly is left for the step that can measure it.

## What each document contains

Every one of them has the same five parts, in the same order:

1. **The step in pseudocode**, and a table of what each library gives it. The
   pseudocode marks every line as ours or as a library's, so it is clear where
   the project's own thinking is and where it is standing on someone else's
   work.
2. **How the step works**, with the project's own arithmetic on the project's
   own glasses.
3. **What went wrong** when that step was first put in front of a simulator,
   and what was done about it. Worth reading before changing anything near the
   simulator. Almost none of these faults announced themselves anywhere near
   where they lived: a missing line in a model file arrived as an arm that
   could not plan a path, and a texture drawn at the wrong angle arrived as a
   glass lowered onto bare table.
4. **Where the current approach can fail.** What the step assumes, and what
   happens when the assumption does not hold. These are the sections to read
   before trusting any of this outside the simulator — they cover unknown
   objects on the table, real glassware, wet glass, and the places a number was
   chosen rather than derived.
5. **How else it could have been done** — the models, the frameworks and the
   classical methods that could have stood in that step's place. What each
   would be good and bad at here, and why the code does what it does instead.
   These comparisons are the quickest way to see what the project trades away.
   It is usually the same trade: accuracy on a hard real-world case, against
   being able to say why a glass was refused. For steps 1 and 4 this part
   grew long enough to have its own document, `step1-approaches.md` and
   `step4-approaches.md`, and the step document links to it.

## The six

- [**Step 1 — finding the glasses**](step1-finding-the-glasses.md). How a
  picture of distances becomes places in the room. Why a glass is simply
  something standing above the table, once you assume it is opaque. What keeps
  the rack and the arm's own fingers out of the answer. And why one look from
  above is not enough.
  - [Other ways to find a glass](step1-approaches.md): the current method
    beside twelve others, from fixed cameras and feeling with the fingers to
    the ways of finding a glass that really is glass, explained from the start.
- [**Step 2 — measuring one**](step2-measuring-one.md). One picture from the
  side, and why one is enough. Pixels to millimetres using a distance the arm
  knows for a reason that has nothing to do with the glass.
- [**Step 3 — what kind of glass is it**](step3-what-kind-of-glass.md). Reading
  the kind off the measured profile with three tests, and why this is both
  cheaper and more honest than classifying from above.
- [**Step 4 — where to hold it**](step4-where-to-hold-it.md). Three rules, the
  features they read, the ways an answer gets rejected, and why the opening is
  never a number from a file.
  - [Other ways to choose where to hold it](step4-approaches.md): ranked
    search, touch, grasp networks and learning, and which of them to try next.
- [**Step 5 — how hard to squeeze**](step5-how-hard-to-squeeze.md). Why the
  weight of a glass cannot be seen, what the estimate is good for, and the
  ten-millimetre lift that settles it.
- [**Step 6 — turning it over and standing it down**](step6-turning-it-over.md).
  Rotating about the grip rather than the wrist, the wrist limit that has to be
  checked before the fingers close, the tilt budget, and feeling for the rack.

## Reading a run against these pages

Every run writes its own account of itself into `runs/<when>/report.md`, and it
is laid out to be read beside these six documents. Its headings are the six
steps, in order. Under each one, the lines in **`bold code`** are the lines of
that step's pseudocode block, word for word, each followed by what that line
produced on that run — the real distance, the real width, the real picture.

So a number in a report can always be traced to a line of pseudocode, and a
line of pseudocode can be watched happening. `test_report.py` is what keeps the
two the same: it reads every line the report writes and fails if one of them is
not in some step's pseudocode block. Reword one side and the test asks you to
reword the other.

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
