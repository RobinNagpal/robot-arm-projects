# Solution 3 — imitation from the teacher's own demonstrations

> **What it uses** — PyTorch and LeRobot's ACT, through
> [problem 4's examiner](../the-examiner.md). **Two models are fitted here from
> random numbers**, on demonstrations collected in this cell. Nothing is
> downloaded.
> **What it does** — it watches the ranked geometry solution clear three hundred
> tables and records every answer it gave. One small model is then fitted to
> decide *what kind* of answer to give and at which glass, and a chunked policy
> is fitted to draw the path for a decision it is handed.
> **How it differs from the others** — it is the only solution here that learns
> *what to do* from a teacher that already does it well. The world model learns
> what a push does and then searches; this one learns the answer directly.
> **What it costs** — eight minutes of the arm's own time to collect eleven
> thousand demonstrations, twenty minutes of a laptop to fit the three gates and
> about three hours to fit the three policies. Answering is cheap.

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

The first version of this solution was a single network fitted to copy that
teacher, and **it freed no glasses at all**: not one table separated and not one
glass given room it did not start with. That result was not a fault in the
fitting, and the next two sections explain why. It is a property of what the
task became once the overhead camera was taken away, and it pointed at a
particular repair.

By the end of this page you will understand that cause, the three changes made
because of it — splitting the decision away from the drawing, teaching the rare
answer to count as much as the common one, and writing a push down in the frame
of the glass it pushes — and what each of them bought when the solution was
measured again.

## A film of one table

Here is the first of the three fits on one table. The film was recorded in the
simulator and plays at one and a half times real speed.

[Watch the film (5 s)](../../../videos/04-clear-the-table/03-imitation-from-demonstrations.mp4)

It is table 10001 of the held-out fifty, the one table every solution in
problem 4 is filmed on, and
[the comparison page](../../../04-clear-the-table/results/README.md#a-film-of-each-solution)
says how the table was chosen and how to read a film. It is worth watching
beside [the teacher's own film](02-geometry-ranked.md#a-film-of-one-table) of
the same table, because the teacher separates it and the student does not.

The film is short, and what it shows is this solution's remaining weakness
rather than its progress. The student gives nine answers in nine arm seconds,
none of them comes down to a glass, the gate then says the table needs nothing
more, and two of the four glasses are still short of room. All three fits do
the same thing on this table, which is why the film is of the behaviour and not
of one unlucky run.

Two things in it are worth watching for, and both are honest.

**Nothing is broken, and the hand is never carried across the table at the
height of the glasses' rims.** That was the commonest way this problem's fitted
solutions broke glass, and the clearance arithmetic described below is what
removed it. Every answer in this film either rides clear above the glasses or
is not drawn at all.

**The gate stops too early here.** It has learned the teacher's declaration
well — it finds the teacher's own "finished" in nine or ten cases out of ten —
and on a table like this one it also offers that declaration when the teacher
would still have been probing. That is the shape of the gate's error: it is
accurate about the common answers and it is still too quick to agree that there
is nothing to do.

## What a demonstration is here

A demonstration is one pair: what the solution was shown, and what the teacher
answered.

What the solution is shown is a **look**, which holds the picture the camera on
the arm took from where the jaw is standing, the glasses that are inside that
picture with their measurements, where the jaw is standing, and how much arm
time is left. What the teacher answers is a **path for the jaw**: a list of
waypoints the arm is to follow, which may be a push into a glass or may only be
a move to a new place to look from.

The collector now writes down two more things about every answer, and they are
what makes the rest of this page possible. The first is **which kind** of answer
it was, out of four: a move to go and look, a five-millimetre probe into a glass
to test whether it will slide, a push at the task, or the statement that the
table is finished. The second is **which glass** the answer was aimed at, given
as a position in the list of glasses the picture caught, with one extra value
meaning "none of them". A look is aimed at nothing. A push is aimed at exactly
one glass.

Both halves have to become fixed-size arrays of numbers before a network can be
fitted on them, and the choices made there matter more than they look.

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

Eleven thousand three hundred demonstrations from three hundred tables, drawn
from table one thousand onwards, which is well below the held-out band. A
further set was collected from fifty tables the fitting never sees, so that
copying can be told apart from learning.

**Collecting cost eight minutes of arm time for the fitting set**, which is
about one and two thirds of a second a table and about thirty-seven answers off
each table. That is worth comparing with problem 3, where a table cost three
quarters of a second. So a *table* costs more than twice as much here, because
the teacher has to travel to see before it can push, and travelling is arm time.

That difference has a shape worth naming. **The set is wide in frames and narrow
in pushes.** It holds more demonstrations than problem 3's from a fifth as many
tables, and only three hundred and fifteen of them are pushes at the task
against problem 3's seven thousand. The reason is the next section, and it is
the reason for everything that follows.

## Four answers in five only move the arm to see

With the camera above the table, a solution looks once and then pushes. With the
camera on the arm, a solution has to travel to see, so most of what it does is
travelling.

Measured on the collected set, **seventy-nine per cent of the teacher's answers
are looks**: paths that move the jaw to a new viewpoint without coming down to
any glass. A probe, which is a short test shove to find out whether a glass
slides or tips, is about one answer in six. A push at the task — the answer that
actually gives a glass room — is **one answer in thirty-six**.

This is not a flaw in the teacher. It is what the task is, once the overhead
camera is taken away, and the whole point of problem 4 was to find out what
happens when a solution has to pay for knowing. But it is fatal to plain
copying, for a reason that belongs to fitting rather than to the robot.

**Fitting a network on examples teaches it the average example.** A network
fitted to minimise the distance between its answer and the teacher's answer
will, wherever the input does not clearly tell the two kinds apart, produce
something between them — and when four examples in five are looks, something
between them is a look. This is the same effect as fitting a straight line
through a cloud of points that is mostly on one side: the line goes where the
weight is. So the student learned the travelling, which is most of the data, and
not the pushing, which is the part that changes the table.

## One model decides, the other draws

The repair follows directly from that cause. If the trouble is that one network
has to produce two very different kinds of answer out of one output, and fitting
makes it answer with the average of them, then **give the two jobs to two
models**.

The first model is called the **gate**, because it stands in front of the policy
and decides what passes through it. It is shown exactly what the policy is
shown, and it answers two questions: which of the four kinds of answer to give,
and which glass to give it at. It is small on purpose — a few convolutions over
the picture, the numbers joined on at the end, and two output heads — so one fit
of it takes seven minutes rather than the hour the chunked policy takes.

The second model is the chunked policy, unchanged from problem 3 except that the
decision is now part of what it is shown. It no longer has to work out whether
this is a moment for looking or for pushing, because it is told. Its only job is
to draw the path for the kind of answer it has been handed.

The comparison worth holding on to is a **classifier in front of a regressor**.
Choosing between named things and predicting a position are different problems
with different loss functions, and a loss that averages positions cannot express
"these two answers are not on a line between each other". Separating them lets
each loss do what it is good at.

The gate is also where "the table is finished" now comes from. The teacher
answers a table it considers done with a statement rather than a path, the
collector records that answer, and so "done" is one of the four things the gate
chooses between. In the first version the solution had no way to say it at all
and relied on the examiner's rule that a long quiet spell means finished —
which declared nine of its ten tables finished while they were still crowded.

### The gate had to be taught that a rare answer still counts

Splitting the models is not enough on its own, because the first fit of the gate
reproduced the same failure in a smaller form: it learned three of the four
kinds and **never once answered "push"**. That is the right thing to do if the
goal is to be wrong as rarely as possible, since only one answer in thirty-six
is a push, and it is useless as a decision, because the push is the answer that
changes the table.

Two changes fixed it, and both are about what the loss is asked to care about.

**Each kind is weighted by how rare it is.** Each kind's part of the loss is
divided by how many examples of that kind there are, so a missed push costs as
much as a missed look. Being wrong in the other direction is cheap here: a push
proposed where none was needed is a short shove at a glass that did not need
moving, and the clearance check described below still stands in front of it.

**The head that names the glass is asked only about answers that name one.** A
look and a "done" are aimed at nothing, so a head trained on every frame spends
most of itself learning to answer "none". The first fit did exactly that: it
named the right glass eighty-five per cent of the time over all frames and
seventeen per cent of the time on the frames where a glass was really chosen.
The frames that name no glass are now left out of that head's loss, so it learns
the one thing it is used for — given that something is to be acted on, which
glass is it?

Measured on tables the fit never saw, over the three fits:

| | over the three gates |
| --- | --- |
| the kind right | 70% to 71% |
| the glass right, over the answers that name one | 56% to 61% |
| the teacher's probes found | 49% to 68% |
| the teacher's pushes found | 56% to 77% |
| "finished" found, of the teacher's declarations | 92% to 96% |
| pushes offered, of all its answers | 16% to 21% |

Two of those rows are the point of the change. The gate now finds most of the
teacher's pushes, where before it found none, and it offers a push about one
answer in five against the teacher's one in thirty-six. It is deliberately
eager, and the two rows have to be read together: being eager is how a rare
answer survives fitting at all, and the cost of an unnecessary push is small.

### A push is written down in the frame of the glass it pushes

The third change is about what the policy has to learn, and it is the cheapest
of the three.

A push is the same movement wherever on the table it happens: come down beside
the glass and shove it away from its neighbour. Written in the table's own
coordinates, that one movement looks like a different answer for every place a
glass can stand, so the policy has to learn the movement once for each position.
Written as an offset **from the glass it is aimed at**, it is one answer.

This is possible only because the gate names the glass. The policy draws the
path measured from that glass, and the solution adds the glass's place back on
before handing the path to the arm. The idea is the same one behind choosing good
coordinates for a physics problem: the motion is simple in the frame that moves
with the object, and complicated in the frame that does not.

One practical point is worth recording, because it cost a day. The
demonstrations are shared with [solution 6](06-smolvla-fine-tuned.md), which
reads the same files and does not have a gate to name a glass, so the stored
answers cannot be relative. The demonstrations therefore keep one convention —
every path is written in the table's own coordinates — and this solution's
*training script* converts a push into its glass's frame as it builds each
batch. The convention lives with the data, and each solution reads it the way it
needs.

### Every answer is checked for clearance before it is handed over

The last change is shared with two other solutions rather than belonging to this
one, and it is why nothing here breaks glass.

Most of the glasses this problem broke on its early walks were not broken by a
push aimed badly. They were broken by the hand **travelling across the table at
the height of the glasses' rims**, because the fingers hang about seven
centimetres below the point a waypoint names, so a path at a comfortable looking
height sweeps the rims of everything it passes over.

So before a drawn path is handed to the arm, this solution checks it against a
rule written once in the examiner's folder and run by the solutions rather than
by the examiner. The rule asks a path to account for itself: a path that only
travels must ride at travel height, and a path that comes down must come down to
the glass the gate named and nowhere else. A path that cannot account for itself
is **raised to travel height**, where it goes to the same place and touches
nothing.

This is not the examiner refusing an answer. The examiner's own interlock is
unchanged, and it still refuses only a path driven into a glass that would tip.
The clearance rule is arithmetic the solution runs over its own answer, which is
why the same rule is used by the two borrowed-model solutions as well, and why a
run records how many answers were raised and for which reason.

## What the fitting did, and what the two distances now say

Three copies of each model were fitted, because one fit is not a measurement.
The gate is small, so one fit of it takes four thousand steps and about seven
minutes. The chunked policy is the expensive half: eight thousand steps at a
batch of sixteen, fifty-seven minutes a seed, so two hours and fifty-two
minutes for the three. The policy's loss falls from about seven to about six
hundredths, so the fitting converges.

Then comes the measurement that says what kind of learning happened, and the
answer has changed from the first version of this solution. The distance is
measured between the student's waypoints and the teacher's, on two sets of
tables: the ones it was fitted on, and fifty it has never seen.

| the policy against its teacher | a waypoint, on tables it was fitted on | a waypoint, on tables it never saw |
| --- | --- | --- |
| the first version, one model | 18 to 19 mm | 18 to 21 mm |
| this version, told the kind and the glass | 9 to 10 mm | 24 mm |

**The first version had no gap between the two columns, and this one has a
gap of about fifteen millimetres.** That difference is worth understanding,
because the two versions invite opposite conclusions about what to try next.

The first version was equally close on both sets, which means it had learned a
habit rather than a set of tables — and the habit it had learned was the
average answer, which is a look. More demonstrations of a habit teach the same
habit, so collecting more would not have helped.

This version is told which kind of answer to draw, so it is no longer free to
answer with the average, and it is now genuinely trying to draw pushes. On the
tables it was fitted on it draws them to within about nine millimetres, which
is twice as close as before. On tables it has never seen it is about
twenty-four millimetres out, and on the pushes alone the direction it draws is
about twenty-two degrees away from the teacher's. So this version is short of
examples in a way the first one was not, and more demonstrations — especially
more pushes, which are one answer in thirty-six — are now a reasonable thing to
try.

## What the held-out queue measured

Fifty tables offered in order from table ten thousand, fifteen minutes of arm
time for the whole queue, walked once for each of the three fits. The "before"
column is the same measurement of the first version of this solution, which is
the single network with no gate.

| | before | now |
| --- | --- | --- |
| tables attempted | 10, from 1 to 11 | 12, from 12 to 15 |
| tables separated | **0** | 0, from 0 to 1 |
| glasses made pickable | **0** | **+1**, from +1 to +2 |
| glasses broken | 0 | 1, from 1 to 2 |
| pickable share at the end | 0.400 | 0.400, from 0.378 to 0.404 |
| said it was finished while the table was still crowded | 9 | 9, from 9 to 11 |
| thinking an answer | 16 ms | 18 ms |

**The solution now acts, where before it only looked.** That is the whole of
what the changes bought here, and it is a real change rather than a
rearrangement of the same result: the first version handed back every table
exactly as it was drawn, and this one gives one or two glasses room they did not
have and separates a table in one walk of three.

**The share is the same number as before and it means something different.**
0.400 for the first version was the glasses that arrived with room, every one of
them, because it moved nothing. 0.400 now is a solution that frees a glass or
two and breaks one, and the breakage is what holds the number down: a table that
loses a glass pays nothing at either end, so one broken glass costs the whole of
that table's four or five glasses from the count. The gain row and the broken row
together are the honest reading of this solution, and the share on its own is
not.

**Where the spread went.** An earlier version of this solution, with the same
two models and a clearance check shown only the current picture, had walks that
broke two, two and five glasses. Checking instead against every glass it has
measured took that to one, one and two, and tightened every other number with it.
It also cost two of the three glasses it used to free. That trade — half the
breakage for two thirds of the work — is reported in full in
[what changed](../what-changed.md), and it was taken because a toppled glass is
the one outcome this problem treats as unrecoverable.

## The same three fits on twenty tables below the held-out line

Tables 0 to 19, each given four arm minutes of its own, which is how solutions
1 and 2 were measured, so the three can be set side by side. This is not the
scored measurement above and it carries no throughput reading, but it is twenty
tables rather than twelve, so it is where the comparison with the geometry
solutions lives. The ceiling column is what the ranked chooser reaches with the
arm taken away: true positions, exact pushes and no clock.

| | solution 1 | solution 2 | **solution 3** | ceiling |
| --- | --- | --- | --- | --- |
| tables separated | 5 | 4 | **0 to 1** | 11 |
| glasses pickable at the end, of 84 | 47 | 43 | **31 to 38** | 66 |
| glasses made pickable | +14 | +10 | **−2 to +5** | +33 |
| glasses toppled | 0 | 0 | **1 to 3** | — |
| arm seconds a table | 42.6 | 41.1 | **59 to 71** | — |
| said done while still crowded | 15 of 20 | 16 of 20 | **18 to 19 of 20** | — |

The three fits of one recipe still disagree with each other more than two of
them disagree with doing nothing. One separates a table and frees five glasses
while toppling three; one loses two glasses and topples two; the third frees one
and topples one.

## What topples the glasses, measured rather than guessed

This is the sharpest thing the solution's own record now says, and it took a
small piece of machinery to get at.

**A solution cannot see its own breakages.** Every reading of a glass carries
whether that glass is standing, so it looks as though a solution could notice a
glass on its side and remember what it had just done. It cannot: the table ends
the moment a glass goes over, so the look that would show the damage is never
taken. The measurement script therefore keeps each table's last answer beside
how that table ended, which is the only place the two can be put together.

**All five glasses lost over the three fits followed the same kind of answer.**
Each was a push, aimed at a named glass, which passed the whole clearance check
and was then carried on by the arithmetic until the glass would have room. None
was a look, a probe, or a path the check had raised.

**Two of the five went over while the arithmetic expected almost no
movement** — 0.0 and 3.4 millimetres — so those were glasses that tipped under
the hand rather than glasses driven into a neighbour. And in all five the
picture held two or three glasses on a table of four or five, which says the
solution was acting on a part of the table rather than on the table.

That points at one place to repair rather than at the models: the step that
carries a push on, which is the only part of an answer the arithmetic adds to
what the policy drew.

## The three things that stand in the way of more

Each of these is measured, and each of them is a reason this solution frees one
or two glasses rather than thirty. They are listed because the next person to
work on it should start from them rather than from a new idea.

**One push does not move a glass far enough.** A glass needs about
seventy-six millimetres of room for the hand to get round it. A push the policy
draws, carried on until the clearance rule says the glass has room, moves it
between seven and twenty-five millimetres. The policy's own accuracy on an
unseen table is about twenty-four millimetres, so the thing it is trying to
produce is of the same size as its own error, and a glass needs three or four of
these pushes in a row to be freed.

**Every push has to be tested first, because nothing can be predicted.** The
examiner's rule about whether a glass will slide or tip answers "yes" for no
glass this cell draws: over sixteen hundred drawn glasses it is always either
"no" or "try it and see". So a push at a glass is only allowed after a probe
has shown that the glass slides, which means the solution must spend two
answers on every glass it moves, and the gate has to get both of them right in
order.

**The direction the policy draws is often blocked.** Between eighty-seven and a
hundred and fifty-one times over twenty tables, the path the policy draws would
take the hand through a glass it is not aimed at, so the clearance rule raises it
to travel height and the glass is not moved. The policy is drawing the teacher's
push shape in roughly the right place and in a direction the table does not
allow.

**Why the third one was not repaired.** It could be, and the repair is
obvious: choose the direction arithmetically from the measured neighbours, as
the geometry solutions do, and let the policy draw only the shape. That was not
done, and the reason is what this solution is for. It exists to measure what
copying a teacher achieves when looking is most of the task. A version of it
that chooses the push direction by arithmetic would be the geometry reference
with a learned chooser in front of it, which is a different and probably better
machine, answering a different question.

A gentler version of the same idea *was* tried: when the arithmetic refuses the
gate's first choice of glass, ask the gate for its next choice and draw that
instead, so that the order is still the model's and arithmetic keeps only the
power to refuse. It was measured over twenty tables and it was worse — two, four
and five glasses broken against one, two and three — because the change touches
only about one answer in twenty and those are answers at glasses the gate itself
ranked low, where it is wrong more often than right.

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
| One fixed nudge | 10 of 26 | +25 | 0 |
| Geometry ranked | 7 of 25 | +19 | 0 |
| **This solution** | **0 of 12**, 1 in one walk | **+1** | **1** |
| A world model | 14 of 40 | +39 | 1 |
| SmolVLA as it downloads | 1 of 11 | +2 | 0 |
| SmolVLA fine-tuned | 0 of 10 | 0 | 1 |

Of the three solutions that answer from a picture, this one does the most work
and is the only one whose work is deliberate. The borrowed model's one separated
table and two freed glasses come from shoves that happened to go the right way;
this solution chooses a glass, tests it, and pushes it, and the glass it frees is
the glass it chose.

The comparison that really matters is still with its own teacher. The teacher
separates seven of the twenty-five tables it reaches. The student, fitted on
eleven thousand of that teacher's answers and able to reproduce them to within
nine millimetres on tables it was fitted on, separates one table in one walk of
three. The gap between those two sentences is the result of this solution, and
it is now a gap rather than a wall.

## What to take from it

**Copying a teacher copies what the teacher mostly does, not what the teacher
is for.** Four fifths of the teacher's behaviour is travelling to see, and
fitting cannot tell purpose from frequency. This is the finding of the first
version and it has not been overturned; what has changed is that it can be
worked around.

**The way around it is to stop asking one model for two kinds of answer.**
Deciding which kind of answer is wanted is a choice between named things, and
drawing the path is a prediction of positions. Given to one network with one
loss, the choice is answered by the average of the kinds, which is a look.
Given to two models, each loss does what it is good at, and the pushing becomes
learnable. That single change, with the rare answer weighted up so that the
decision does not collapse onto the common one, is what moved this solution
from nothing to something.

**What is learned and what is arithmetic has to be decided on purpose.** This
solution now hands three jobs to arithmetic that it could have learned: that a
travelling path rides high, that a push reaches only the glass it names, and
that a push carries on until the glass has room. Each was given away for a
measured reason, and the one that was *not* given away — the direction of the
push — is the one that now holds the solution back. That is the trade this
method is really about, and it is more interesting than any number on this
page.

**The remaining weakness is the size of one push against the room a glass
needs.** Freeing a glass takes three or four of the pushes this policy draws,
and its own error is as large as one of them. That is a quantity to attack, and
it is a more useful thing to know than "behaviour cloning does not work here",
which is what the first version of this page had to say.

**And a safety rule and a work rule pull against each other, so the trade has to
be stated rather than hidden.** Showing the clearance arithmetic every glass the
solution has measured, instead of the glasses in the current picture, halved the
broken glasses and cost two thirds of the glasses freed. Both halves of that are
in the numbers above. The reason the trade was taken is that this problem treats
a toppled glass as unrecoverable — a table that loses one pays nothing at either
end — so a solution that breaks less is worth more even when it does less.

## Where to go next

- [What changed, and what each change bought](../what-changed.md) — the twelve
  changes made to this problem's fitted solutions, each beside the measurement
  that justified it, including the three that were measured and thrown away.
- [The six solutions side by side](../../../04-clear-the-table/results/README.md)
  — every row, with what perfect play achieves on the same tables as a scale.
- [The examiner](../the-examiner.md) — the draw, the arm's clock, the camera on
  the wrist, and how a walk of tables is marked.
- [The same method in problem 3](../../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md)
  — where the method itself is explained, and where it had an overhead camera.
- [The world model](04-a-world-model.md) — the other solution fitted entirely
  in this cell, which learns what a push does instead of what to do.
