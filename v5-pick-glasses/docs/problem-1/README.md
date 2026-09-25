# Problem 1 — the walkthrough

Six documents, one per stage of a run, in the order the arm does them. Read
[`problem.md`](problem.md) first if you have not: these six explain *how* one
glass is picked up and racked, and that one explains what is being asked and
what is deliberately absent from it.

This is the only one of the [five problems](../../problem-statement.md#five-problems-in-order-of-difficulty)
that is built. The other four are in the folders beside this one.

## The arc

The six stages are not a list of features. Each one exists because the stage
before it deliberately stopped short, and following that thread is the fastest
way to understand the design.

The arm begins knowing nothing about the table.

**Step 1** finds the glasses from above. It produces a position and a rough
width for each, and nothing else, because from overhead a tall glass and a
short one look the same. It can find them at all because the glasses here are
opaque. That is an assumption the [problem
statement](../../problem-statement.md) sets out, not a fact about glassware, and
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
   being able to say why a glass was refused. For steps 1, 2, 4 and 6 this
   part grew long enough to have its own document, `step1-approaches.md`,
   `step2-approaches.md`, `step4-approaches.md` and `step6-approaches.md`, and
   the step document links to it.

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
  - [Other ways to measure a glass](step2-approaches.md): several
    silhouettes, photogrammetry, radiance fields, laser scanning, and fitting
    a shape.
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
  - [Other ways to turn a glass over](step6-approaches.md): why a glass swings
    in two flat pads, and the turns, grips and pads that would stop it.

## What does not work yet

[`../known-gaps.md`](../known-gaps.md) lists the failures that are known but
not yet fixed, such as the glass sizes the grip rules cannot handle.

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

## Where the techniques come from

None of the perception here is invented for this project. Each step is one named
technique, and the place they are all set out side by side — what each is for,
what it costs, and the five jobs it cannot do — is the **object perception**
area of [robotics-basics](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/01_overview.md). Every step document links to the
sections it uses, and this is the map:

| Document | What this project takes from it |
| --- | --- |
| [Overview](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/01_overview.md) | why one picture has no size, the pixels-to-millimetres calculation every measurement here reduces to, and the three ways to supply the distance it needs |
| [The sensors](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md) | why a depth camera fails on real glass, what a wrist force sensor can and cannot tell you, and why calibration is usually the largest error |
| [Methods you write yourself](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md) | almost all of this project: the plane an object stands on, connected components, ArUco markers, silhouettes of a solid of revolution, and measuring by touch |
| [Models that find](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md) | the alternatives each step turned down — mask models, Segment Anything, open-vocabulary models, and grasp networks |
| [Models that measure](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/05_models-that-measure.md) | learned depth, stereo matching, pose from a CAD model, and reconstruction |
| [Licences and platforms](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/06_licences-and-platforms.md) | which of those may actually be shipped, and what runs on a Mac |
| [Making it work](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/07_making-it-work.md) | why mAP is not the metric for an arm, the diagnosis ladder, and what a simulator will not tell you |

Steps 4, 5 and 6 are gripping rather than perception, and they have their own
area: [gripping](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/01_overview.md).

| Document | What this project takes from it |
| --- | --- |
| [Overview](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/01_overview.md) | the six ways to hold something, what a grip has to survive, and the three things every tutorial leaves out |
| [Grippers and hardware](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/02_grippers-and-hardware.md) | how to read a datasheet, why the force you command is not the force you get, and the sensors that go on a gripper |
| [Choosing a grip](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md) | the friction arithmetic behind step 5, rules from a measured profile, bounding the search by the gripper's own body, and how to test a grip rule |
| [Models that grasp](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/04_models-that-grasp.md) | the grasp networks step 4 turns down, and which of them may be shipped |
| [Holding on](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md) | the five-step squeeze sequence, what a finger-gap slip check cannot see, and the release sequence |
| [The two-finger gripper](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/06_two-finger-gripper.md) | this cell's gripper, its ROS 2 interfaces, and the grasp written out as pseudocode |
| [Licences and platforms](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/07_licences-and-platforms.md) | what may be shipped, and what runs without CUDA |

There is also a design document for this exact task, written before any of the
code: [standing an empty glass upside down on a drying
rack](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/10_one-arm-training/07_case-study/01_place-glass.md).
It is worth reading against what was actually built, because the two have
diverged — most of all on transparency, which that document assumes and this
project now does not.

## The pictures

Every picture these six documents use is drawn by
[`images/generators/make_images.py`](../../images/generators/make_images.py), which imports the project's modules
and plots what they return. Nothing is illustrative. If a rule changes, the
pictures change with it the next time it is run, which is the only way a
diagram stays true.

The diagrams in the *problem* documents, here and in the folders for problems 2
to 5, come from [`images/generators/make_problem_images.py`](../../images/generators/make_problem_images.py)
instead, and that promise does not hold for them: a problem that is not built
has no function to plot. They are drawn from the geometry written beside them.

## Where to go next

For what this problem is and what it leaves out, read
[`problem.md`](problem.md). For the reasoning behind these choices, read
[`../../implementation-notes.md`](../../implementation-notes.md). For which
file and function each stage lives in, read
[`../../pseudocode.md`](../../pseudocode.md). For the other four problems, read
[`../README.md`](../README.md).
