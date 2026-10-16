# Solution 3 — imitation from the teacher's own demonstrations

> **What it uses** — PyTorch and LeRobot's ACT, through
> [problem 4's examiner](../the-examiner.md). Three copies of one network,
> fitted in this cell on demonstrations collected in this cell. Nothing is
> downloaded.
> **What it does** — it watches the ranked geometry solution clear three
> hundred tables, records every answer that solution gave, and fits a network
> to answer the same way. Then it is asked to clear tables on its own.
> **How it differs from the others** — it is the only solution here that learns
> *what to do* from a teacher that already does it well. The world model learns
> what a push does and searches; this one learns the answer directly.
> **What it costs** — nine minutes of the arm's own time to collect eleven
> thousand demonstrations, and three and a half hours of a laptop to fit three
> copies. Answering is cheap, at sixteen milliseconds a turn.

> **The cell is described once, in [the cell](../../the-cell.md).** The method
> itself — what behaviour cloning is, what an action chunk is, and why ACT
> predicts a whole sequence of moves instead of one — is described once in
> [problem 3's page for the same method](../../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md).
> This page covers only what problem 4 changes, and what problem 4 measured.

## Introduction

This page answers [problem 4](../problem.md) by copying a teacher.

The idea is the oldest one in machine learning for robots and it is still the
first thing anyone tries, because it asks for so little. You do not need to say
what a good push is, you do not need a model of the physics, and you do not
need a reward. You need a teacher that can already do the job, and a network
large enough to remember what the teacher did. Problem 4 has such a teacher
already: the [ranked geometry solution](02-geometry-ranked.md) separates tables
with arithmetic and no learning at all, so it can be asked to clear as many
tables as anyone has patience for, and every answer it gives is a free label.

By the end of this page you will know what was collected, what was fitted, and
why the result is zero: not one table separated and not one glass given room it
did not start with. The reason turns out to be a property of **problem 4's
task** rather than a fault in the fitting, and it is the most useful thing this
solution found.

## A film of one table

Here is one of the three fits clearing one table, or rather not clearing it.
The film was recorded in the simulator and plays at one and a half times real
speed.

[Watch the film (12 s)](../../../videos/04-clear-the-table/03-imitation-from-demonstrations.mp4)

It is table 10001 of the held-out fifty, the one table every solution in
problem 4 is filmed on, and this is the first of the three fits.
[The comparison page](../../../04-clear-the-table/results/README.md#a-film-of-each-solution)
says how the table was chosen and how to read a film. The film is worth
watching beside [the teacher's own film](02-geometry-ranked.md#a-film-of-one-table),
because the teacher separates this table and the student does not.

Three things in it are worth watching for, and together they are this page's
result.

**No glass gains room.** The student gives twenty-five answers over fourteen
arm seconds, and the table it hands back is the table it was given: two of the
four glasses had room at the start and two have room at the end. That is what
"freed no glasses" means on one table.

**Almost every answer is a single waypoint.** Twenty-three of its twenty-four
paths hold one point each, which is
[the habit described below](#the-fit-that-put-its-hand-down-and-called-it-an-answer).
On this table those twenty-three all stay above the glasses, so the arm hovers
and the picture in the corner is the only thing that changes.

**The one real answer comes down in the right place and still moves nothing.**
Answer nine is a path of thirty-nine waypoints that descends to exactly the
height the jaw pushes at, and the writing across the top marks it as a push. So
the failure a viewer sees here is not the student holding its hand too high. It
is a properly shaped push aimed where no glass needs moving, and after it the
student goes back to hovering and then says it is finished.

## What a demonstration is here

A demonstration is one pair: what the solution was shown, and what the teacher
answered.

What the solution is shown is a **look**, which holds the picture the camera on
the arm took from where the jaw is standing, the glasses that are inside that
picture with their measurements, where the jaw is standing, and how much arm
time is left. What the teacher answers is a **path for the jaw**: a list of
waypoints the arm is to follow, which may be a push into a glass or may only be
a move to a new place to look from.

Both halves have to become fixed-size arrays of numbers before a network can
be fitted on them, and the choices made there matter more than they look.

**The picture is the wrist view, not an overhead view.** This is the whole
difference between problem 4 and problem 3, and it is why this solution had to
be built again rather than copied across.

**The answer is the commanded path, padded to a fixed length, with one extra
number saying where the path ends.** Padding rather than resampling is a
deliberate choice: resampling a path to a fixed number of points would move the
waypoints, and the arm's own timing rule charges a path by how far apart its
waypoints are, so resampling would change the speed the student asks for and
round off the sharp corner at the bottom of a descent. The extra number is what
lets the student say "my path is shorter than the array", which padding alone
cannot express.

## What was collected, and what it cost

Eleven thousand and sixteen demonstrations from three hundred tables, drawn
from table one thousand onwards, which is well below the held-out band. A
further one thousand eight hundred and fifty were collected from fifty tables
the fitting never sees, so that copying can be told apart from learning.

**Collecting cost eight and a half minutes of arm time for the fitting set.**
That is about one and three quarter seconds a table and five hundredths of a
second a demonstration, and it is worth comparing with problem 3, where a table
cost three quarters of a second and a demonstration cost just over half a
second. So a *table* costs more than twice as much here, because the teacher
makes about six pushes a table against problem 3's three, and a push is where
the settling time goes. But a *demonstration* costs a tenth as much, because
every single answer is a demonstration and about thirty-seven of them come off
one table.

That difference has a shape worth naming. **The set is wide in frames and
narrow in pushes.** It holds more demonstrations than problem 3's from a fifth
as many tables, and only about two thousand of them are pushes against problem
3's seven thousand. The reason is the next section, and it is the reason for
everything that follows.

## Four answers in five only move the arm to see

With the camera above the table, a solution looks once and then pushes. With
the camera on the arm, a solution has to travel to see, so most of what it does
is travelling.

Measured on the collected set, **eighty-one per cent of the teacher's answers
are looks**: paths that move the jaw to a new viewpoint without coming down to
any glass. Only about one answer in five is a push.

This is not a flaw in the teacher. It is what the task is, once the overhead
camera is taken away, and the whole point of problem 4 was to find out what
happens when a solution has to pay for knowing. But it is fatal to copying, for
a reason that belongs to the fitting rather than to the robot.

**Fitting a network on examples teaches it the average example.** A network
fitted to minimise the distance between its answer and the teacher's answer
will, wherever the input does not clearly tell the two kinds apart, produce
something between them — and when four examples in five are looks, something
between them is a look. This is the same effect as fitting a straight line
through a cloud of points that is mostly on one side: the line goes where the
weight is. So the student learns the travelling, which is most of the data, and
not the pushing, which is the part that changes the table.

## What the fitting did, and that it worked

The fitting itself is not where the problem is, and it is worth establishing
that before blaming it.

Three copies of the network were fitted, because one fit is not a measurement.
Each took eight thousand steps and between sixty-seven and seventy-eight
minutes, which is three and a half hours in total. The loss fell from about six
to about nineteen hundredths, so the fitting converged.

More importantly, the fits **generalise**. The distance between the student's
waypoints and the teacher's is about nineteen millimetres, and it is the same
on tables the student was fitted on as on tables it has never seen. A network
that had memorised its examples would be close on the first and far on the
second. So this student has learned the teacher's habit rather than the
teacher's tables, and that tells you something useful about what to try next:
**collecting more demonstrations would not help**, because the student is not
short of examples, it is faithfully reproducing the wrong average.

## What the held-out queue measured

Fifty tables offered in order from table ten thousand, fifteen minutes of arm
time for the whole queue, walked once for each of the three fits.

| | over the three fits |
|---|---|
| Tables attempted | 10, from 1 to 11 |
| Tables separated | **0** |
| Glasses made pickable | **0** |
| Glasses broken | 0 |
| Pickable share at the end | 0.400, from 0.25 to 0.405 |
| Said it was finished while the table was still crowded | 9 |
| Thinking an answer | 16 ms |

All three fits spend the whole fifteen minutes and change nothing.

**Read the share of 0.400 carefully, because it is the one number here that
flatters.** It is not partial credit for partial work. The glasses that have
room at the end are exactly the glasses that had room when the table was drawn,
which the line above it states: zero glasses made pickable. A share of 0.400
and a gain of zero together mean the student left the table as it found it.

**The spread between the fits is throughput and not quality.** One fit reached
eleven tables and another reached one, which looks like a large disagreement.
But the one that reached a single table never said a word on it and was stopped
by the clock after a thousand answers, and on the single table all three
reached, all three left its four glasses with one pickable and two of them
declared themselves finished. So the walks are comparable on one table and no
further, and the 0.25 against 0.405 is one table's denominator against eleven
rather than a difference in what the fits do.

## The fit that put its hand down and called it an answer

One of the three fits does something revealing. It emits a path of a **single
waypoint** every single time, five and a half thousand times over twenty
tables.

The obvious reading is that it has learned to stand still and look, which would
be the harmless version of learning the average. That reading is wrong, and a
sharpening of the examiner's own rule is what showed it.

The rule that decides whether an answer counts as a push asks whether any part
of the hand on that path comes low enough to touch a glass. It originally asked
about the number a waypoint carries, and that number is the **middle of the
jaw**, while the fingers hang about seventy millimetres below it. Once the rule
was corrected to ask about the fingers, and to ask against the tallest glass
the solution has actually measured, **nearly nine of those ten single waypoints
count as pushes**. The fit is not standing clear of the glasses. It is putting
the hand down among them and calling it an answer, and it gets away with
breaking nothing only because a single waypoint goes nowhere.

This is the clearest example in the project of why a measuring rule has to be
written against what the machine really does. Under the old rule the same fit
looked like a well-behaved policy that only ever looked.

## What this solution contributed to the examiner

Two parts of problem 4's examiner exist because this solution needed them, and
both are better for it.

**The teacher's quiet spells are now a measurement rather than a guess.** A
policy has no word for "finished", so the examiner reads a run of answers that
would not touch a glass as the policy saying it has nothing to do. How long
that run must be was originally set at three, which was picked rather than
measured. Measured on forty tables of the demonstration band, with every answer
classified by the examiner's own rule, the teacher's longest quiet spell that
then ends in a push is **eight** answers, and the spell it finishes a table
with is **eleven** at its longest. At three, any solution was being declared
finished partway through its first look round the table, on every table. The
threshold is now sixteen, which sits above both, and the measurement is
committed beside the solution so the number can be checked rather than
believed.

**A refused answer advances no clock, so a deterministic policy repeats itself
for ever.** When the cell declines to drive the jaw into a glass it judges
would tip, the arm does not move, so the table the solution is shown next is
the table it was just shown. A solution that computes its answer will compute
the same answer, and nothing in the loop would ever end. The examiner does
carry a field saying why the last answer was refused, but a trained policy
cannot read a sentence of English, so for this solution and the two borrowed
models that field is unusable. What actually breaks the loop is the cap on how
many answers a table may have, and that cap is worked out from the arm time
left — which is why a measurement script must never hand a table an unlimited
allowance, however convenient that would be.

## Where it sits beside the others

| | tables separated | glasses freed | glasses broken |
|---|---|---|---|
| One fixed nudge | 10 of 26 | 25 | 0 |
| Geometry ranked | 7 of 25 | 19 | 0 |
| **This solution** | **0 of 10** | **0** | **0** |
| A world model | 11 of 32 | 29 | 8 |
| SmolVLA as it downloads | 0 of 15 | −1 | 20 |
| SmolVLA fine-tuned | 0 of 8 | 0 | 8 |

It is the safest of the three solutions that answer from pictures, and it is
tied with the other two on everything that matters, because all three free
nothing. Its one advantage over them is honest: it breaks nothing, and it
answers fifty times faster than either borrowed model.

The comparison that really matters is with its own teacher. The teacher
separates seven of twenty-five tables. The student, fitted on eleven thousand
of that teacher's answers and provably able to reproduce them to within
nineteen millimetres, separates none. The gap between those two sentences is
the result of this solution.

## What to take from it

**Copying a teacher copies what the teacher mostly does, not what the teacher
is for.** The teacher's purpose is to push glasses apart, but four fifths of its
behaviour is travelling to see, and fitting cannot tell purpose from frequency.

**The fix is not more data.** The student already generalises as well to unseen
tables as to fitted ones, so it is not short of examples.

**The fix would be to change what is counted as an example.** Weighting the
pushes up, or fitting two things separately — where to go and what to do when
you are there — would both attack the actual cause. Neither was tried here,
because the purpose of this solution in problem 4 is to measure what plain
behaviour cloning does when looking is most of the task, and the answer is that
it learns the looking.

## Where to go next

- [The six solutions side by side](../../../04-clear-the-table/results/README.md)
  — every row, with what perfect play achieves on the same tables as a scale.
- [The examiner](../the-examiner.md) — the draw, the arm's clock, the camera on
  the wrist, and how a walk of tables is marked.
- [The same method in problem 3](../../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md)
  — where the method itself is explained, and where it had an overhead camera.
- [The world model](04-a-world-model.md) — the other solution fitted entirely
  in this cell, which learns what a push does instead of what to do.
