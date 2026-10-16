# The examiner — marking the table, not the pushes

## Introduction

Problem 4 asks a solution to clear a crowded table by itself. It is
problem 3's task with two helps taken away. The camera above the table is
gone, so the arm carries its own camera and seeing costs motion. The
push-by-push hand-over is gone, so nothing counts the pushes and the
solution says for itself when the table is finished.

The examiner is the program that sets that task and marks the answer. It
draws the tables, holds the physics the glasses slide and tip in, shows a
solution what the camera on the arm can see from where the arm is standing,
carries out whatever path comes back, keeps the arm's clock, and then marks
the table as it stands when the solution stops.

By the end of this document you will know why there is an examiner at all,
how a table is drawn and why it is drawn that way, what a solution is shown
and what it is not, what it may answer, why saying "done" is part of its
job, what the budget is made of, what the cell will still refuse to do for
it, what happens when a glass goes over, and what every number on the
scorecard is for.

Read this before any solution document, because each of them assumes it.

Nothing has been measured yet. The shared contract and the one module that
borrows from problem 3 are written; the draw, the clock, the arm's camera,
the loop and the scorecard are being built as this is written. So there is
not a single measured number in this document. Where a result would go, it
says so instead.

## Why there is an examiner at all

Problem 4 will be answered more than once, by methods that have almost
nothing in common: arithmetic that computes a push, and policies that were
trained. Two answers can only be set side by side if they were asked the
same question and marked the same way. That is the examiner's whole reason
to exist.

It does that by holding three things fixed. The **tables** are the same
tables, drawn in the same order. What a solution is **shown**, and what it
may **answer**, are the same for all of them. The **marking** is the same
set of counts, computed the same way. Everything a solution is free to
change sits between what it is shown and what it answers, and that middle
part is exactly what is being compared.

Problem 4 gives a solution much more freedom than problem 3 did, and that
makes the fixed edges matter more rather than less. When nothing counts the
pushes, the only thing holding two answers together is the examiner. This
is the ordinary discipline of a controlled experiment: one thing varies,
and everything else is pinned down.

There is a second reason, and it is about the comparison between the two
problems rather than within one. Problem 4 is problem 3 minus two helps, so
the interesting number is the difference between them — and a difference
only means something if the cell underneath is the same cell. The examiner
therefore **imports** problem 3's bench instead of copying it: the same
physics, the same glasses, the same jaw, the same measurement error. A copy
would drift from the original the first time either one changed, and the
comparison would quietly stop being a comparison. Everything borrowed comes
through a single module, so the whole debt to problem 3 can be read on one
page.

## What the examiner draws

The tables are the first of the fixed things, so they come first.

One word needs pinning down before anything else. In this project two
glasses are **touching** when they are too close for the gripper to get
round either of them. That is the only closeness the task cares about, and
[problem 3's problem statement](../03-push-glasses-apart/problem.md)
explains why: the hand is not a point, so it needs clear room all round a
glass, measured to the neighbour's edge rather than to its middle. Glasses
that a person would call separate can still be touching in this sense.

In the physics the glasses never actually overlap: the draw always leaves a
small gap. This is not a detail about appearances, it is about how a contact
solver works. Two solid bodies that start out sharing the same space push
each other apart in the first instant of simulation, so an overlapping table
would begin by moving on its own, before any solution had answered
anything.

With that said, every table holds three to five glasses, and holds them in
a particular mixture.

**One touching group, of either two glasses or three.** A touching group is
a set of glasses standing so close that the hand cannot get between them, and
it is the unit of crowding the whole task is about. A group of two is the
smallest such unit and the one a single push can answer, so a solution that
cannot handle a pair cannot do the task at all. A group of three is a real
step up, because it is not two pairs: moving the middle glass of three can
leave the outer two touching each other, and moving an outer one can push it
into something else, so the three cannot be dealt with one pair at a time and
the order of the pushes matters. It is the same step up as going from two
equations in one variable each to two equations that share a variable, because
each part can no longer be solved on its own. Both sizes appear about equally
often over a long queue, so a solution meets both.

**This draw is the second one, and it is deliberately easier than the first.**
The first draw asked for four to seven glasses with a touching pair *and* a
touching group of three on every table. That turned out to be not merely hard
but unsolvable: with perfect play, choosing the best push available at every
step from exact knowledge of the table, the geometry reference separated none
of twenty tables and ran out of candidate pushes after thirty-one pushes. A
draw on which the ceiling is zero cannot rank anything, because every method
scores zero and the differences between them vanish. So the draw was reduced
until the ceiling was clearly above zero while the task stayed hard, which is
why the tables are smaller now and hold one touching group rather than two.

**One or two glasses that already have room.** These are the glasses whose
correct treatment is to be left alone. Without them, "push everything you
can see" would be a correct policy, and a solution that had learned nothing
about crowding would score as well as one that had. They also give the word
"done" something to mean: a finished table is not an empty table, it is a
table where every glass has room, and some of them had room from the start.

**The amount of crowding stays inside a narrow band.** How many glasses are
crowded is allowed to vary only a little from table to table. If it varied
widely, a method's score would depend heavily on which tables it happened to
draw, and that luck would have to be averaged away with many more tables
than this project can run.

**Every table is solvable in principle.** A pushed glass either slides or
tips over, and which one happens depends on how high up it is pushed, how
wide its foot is, and the friction under it. The examiner checks each
crowded glass against that same arithmetic — the one problem 3's first
solution uses — and draws the table again if any crowded glass is one that
would tip rather than slide. So a crowded glass left at the end of a table
is a choice the solution made, not a table it was given that could not be
done.

That guarantee is deliberately one-sided, and the asymmetry is the heart of
the problem. The examiner knows the friction, because it owns the physics.
A solution never sees it, and nothing in the cell measures it. So the
examiner can promise that a safe push exists, while the solution still
cannot compute which push that is with certainty. It has to push as low as
the hand can reach, and then look at what actually happened.

## Why no two tables are built the same way

The mixture above fixes what a table contains. It must not fix how much of
each, or where.

A trained policy learns whatever is reliably true of its training data,
without any way of telling a fact about the task from a fact about the data
set. If every table held exactly five glasses as one pair and one triple,
then "there is a pair and a triple" would become part of the policy. It
would score well here and fail on the first real table, because what it
learned was this examiner rather than the task. This is the familiar failure
of a multiple-choice test whose answer is always C, or of a cached value
that happens to be right every time it is checked during testing.

So the composition varies with the table's number: how many glasses, which
of them are crowded, how the pair and the group are placed. What stays
roughly steady is the amount of crowding, for the reason the previous
section gave.

Those two pulls look contradictory and are not. One of them varies the
things a policy could memorise instead of learning. The other holds steady
the one quantity that would otherwise swamp the comparison. It is the usual
shape of an experiment: vary what you are studying, hold fixed what would
otherwise explain your result for you.

## What a solution is shown

A solution never sees the table. It sees one **look** at a time, and a look
holds four things: the picture the camera on the arm took from where the jaw
is standing, the glasses that are inside that picture with their
measurements, where the jaw is standing, and how much arm time is left in
this table's budget.

Both kinds of solution are served by that one look. A solution that works
from numbers reads the measurements; a solution that works from pictures
reads the picture. They are the same information about the same moment, in
two forms, so neither kind is given an advantage by the shape of the input.

**A look reaches only as far as the camera does.** This is the whole
difference between this problem and problem 3. There is no call anywhere in
the examiner that hands over the state of the table. The camera is mounted
on the wrist, looking forward and down, so what it catches is a patch of
table in front of the hand and nothing else. A solution that wants to know
what is in the far corner has to take the arm over there and look.

The consequence runs deeper than it first sounds. The arrangement of the
table stops being an input and becomes something a solution has to build up
and remember across looks. It is the difference between having an array in
memory and reading a file through a window a few bytes wide: the same
information is available, but keeping track of it is now the program's own
work. Problem 3 handed over the whole table on every call, and that single
convenience hid most of the work a real cell has to do.

The overhead camera was always the simulator being kind. A real cell has its
camera on the arm. Problem 3 could accept the kindness because it was
studying the push; problem 4 is studying the loop of looking and acting, so
it cannot.

**The measurement error is problem 3's, unchanged.** Problem 4 narrows what
can be seen; it does not change how well a glass is seen once it is in
frame. The positions, heights and widths carry the same error problem 3's
camera work produced. That restraint is what keeps the two problems
comparable: if the error changed too, a difference between problems 3 and 4
could be a different camera rather than a different problem.

The error is fresh on every look, drawn from the table's number and the
count of looks so far. Two things follow. Looking twice is worth something,
because two noisy readings of the same glass average to a better one — the
ordinary gain of repeating a measurement. And because looking is now the
solution's own decision rather than the examiner's, two solutions share only
their first look and diverge after it. In problem 3 every solution's first
look was identical because every solution looked at the same times. Here
only the first one is.

## What a solution answers

A solution answers with one of exactly two things: a **path for the jaw** to
follow, or the **statement that the table needs nothing more**. There is no
third kind.

A path is a short run of waypoints — a position and a heading for the hand,
one after another. It is the one language both families of solution speak
natively. A policy of the modern sort emits a run of waypoints in one go
anyway, because predicting a whole short motion is the mechanism by which
such a policy stays consistent instead of wobbling from step to step. A
solution that would rather think in whole pushes can still do that and
expand its push into a path with the same machinery problem 3 used, which
is borrowed rather than rewritten.

**Moving to see and moving to push are the same action.** This is why a path
is enough to express everything. The camera rides on the arm, so a solution
that wants a better view answers with a path that takes the jaw somewhere it
can see from. A look is not a separate kind of request, and it is not free:
it costs arm time exactly as a push does, which is what it costs on a real
robot. One path can do both, looking on the way to a push.

The effect on the problem is large. In problem 3 information was free and
unlimited, so there was never a reason not to look. Here a solution has to
decide how much of its budget to spend on knowing and how much on doing,
which is a real trade and a decision no earlier problem in this project
asked anyone to make. It is the same kind of accounting as a program that
pays for every cache miss, or an experiment whose measurements cost as much
as the thing being measured.

## Why saying "done" is part of the job

Nothing but the solution ends a table. The examiner does not stop when the
glasses are far enough apart, because knowing they are far enough apart is
the solution's job and not a fact it is allowed to be handed.

That cuts both ways, and both sides have a cost. A solution that never says
it is finished spends its whole budget and is then marked on whatever state
the clock happened to catch. A solution that says it too early is marked on
a table it left crowded. There is no safe default.

This is not bookkeeping. On a real cell nothing tells the arm the job is
over. To know that a table is finished, a solution has to be confident about
the whole table, which means it must have gone and looked at all of it. So
the stopping rule is what forces a solution to close its loop, and it is the
part problem 3's push budget and per-glass hand-over were quietly doing on
every solution's behalf.

The statement of being done carries a reason with it. The reason is written
into the record and never scored. It is there because a table left crowded
on purpose and a table left crowded by mistake read identically in the
counts, and a reader of the results will want to tell them apart.

## The budget is the arm's time, not the computer's

Something has to stop a solution that will not stop itself, and that
something is a budget of **arm time**: simulated seconds of the arm moving.

It is added up leg by leg from the path that was actually carried out,
following the cell's own rule rather than a new one. Each leg of a path
costs either one fixed tick of the arm's controller, or the time the jaw
really needs to cover that leg at its top speed, whichever is longer. So
placing waypoints closer together makes a motion slower, not faster, and
nothing can be hurried past the arm's top speed. Mirroring the cell's rule
matters because a budget computed any other way would not be the cost the
arm really pays.

Why arm time, and not the seconds the solution's code took? Because two
solutions that make the same motions occupy a real cell for the same length
of time, whatever computer they ran on. Laptop seconds are a property of the
machine that was rented; arm seconds are a property of the method's
behaviour. It is the same reason an algorithm is described by the number of
operations it performs rather than by how long it took on one particular
computer: the first number is the same everywhere, and the second is not.

Looking costs arm time too, for the reason the last section gave. This is
what makes the trade between looking and acting real rather than rhetorical.

Thinking time is still recorded, separately, exactly as problem 3 records
it. It is a cost rather than a budget. A method that needs seconds of
computation before every short motion may not be runnable on a real arm at
all, and a scorecard that hid that would be misleading — but it must not be
subtracted from the arm's clock, because the arm is not the thing that was
slow.

### One budget for the whole queue, and the tables it does not reach

That budget belongs to a **queue** of tables and not to a table on its own.
Every solution is handed the same ordered list of tables and the same number
of arm seconds for all of them together, and each table may spend as much of
what is left as it needs. This is deliberate, because it makes speed part of
the score instead of a separate column: a solution that clears a table
beautifully in four minutes reaches fewer tables than one that clears it
roughly in one, and the card shows both halves of that trade.

Working that way creates one case that has to be handled carefully. Near the
end of a queue the clock holds only a few seconds, so a table can be handed
over, be asked for a path, and have that path turned down for not fitting in
the time left. The arm never moves, and the table comes straight back
untouched. Such a table is **not counted at all**, because counting it would
say two untrue things at once: that the solution reached further down the
queue than it did, and that it left every glass on that table crowded, which
would drag down the share of glasses made pickable for a reason that has
nothing to do with the method.

The walk then carries on to the next table rather than stopping, because what
did not fit was one path and not every path. The clock still holds time, and
the next table may be asked for something cheaper that fits inside it, which
is also how a queue in a real cell behaves: an operator who cannot finish one
table moves to the next rather than ending the shift. A table where the arm
did move and then ran out of time is a different thing and is counted, because
that is a real attempt the solution did not finish.

## What the cell still refuses to do

Problem 4 takes work away from the examiner and gives it to the solution.
It does not take everything away, and the line between what is kept and
what is dropped is worth being precise about.

Some limits are simply the shape of the machine. A path the arm cannot
follow is rejected before anything moves: one that goes lower than the hand
can reach without its fingers meeting the table, higher than the height it
travels at, off the table, or longer than the arm's buffer holds. These are
not marks or judgements, any more than a compiler rejecting something that
is not a program is a judgement about the program's quality.

One real judgement is kept. The cell **will not drive the jaw into a glass
the physics says would tip rather than slide**. That is a safety interlock,
and it stays. The push budget, which used to end a table after a fixed
number of pushes, is gone.

The difference between the two is the difference between the machine and the
marking. A real work cell keeps its safety interlocks; it does not keep a
scorecard's counters. An interlock refuses one specific dangerous motion and
takes no decision away from the solution, which still chooses what to do
next and still has to do the whole task. A push budget decides when a table
is over, and when a table is over is now the question being asked — leaving
it in would be answering the exam paper in the margin. A fuse and a billing
quota both cut the power, and only one of them is part of the equipment.

How often the interlock had to step in is recorded, because a solution that
leans on the cell to save it from itself is not the same as one that never
needed saving, and a reader should be able to see the difference.

The interlock is one test at one moment, and it is not a promise that
nothing can fall over. A glass driven into its neighbour can still go over,
and so can one that was nudged while already leaning. That is why toppling
is still counted.

The cell also **never racks a glass**. Problem 3 had a call that lifted a
glass off the table, and clearing was demonstrated by racking every glass.
Here the table ends with the glasses still standing on it, and the question
is whether each one now has room for the hand. So whether a glass is
pickable is **computed** rather than demonstrated: from numbers that belong
to the gripper, and from the width the arm measured during the run. Nothing
about any glass's size is written down anywhere, which is this project's
first rule. Problem 3's examiner is honest that racking was never a full
demonstration either, because it never asked whether problem 1 could have
gripped the glass at all, so less is lost in the change than it appears.

## When a glass goes over

A glass has gone over when it leans further than the cell calls standing.
Nothing shatters in a simulator, but the cell treats a topple as the end of
the table, because on a real table it leaves shards and an arm that will
keep moving through them. This project refuses a doubtful glass rather than
risk that, everywhere, and the examiner marks in the same spirit.

**The table ends there. The run carries on.**

The reason the run carries on is that a run is a sample of tables, drawn in
order to measure a method. A rule that threw the whole run away on the first
topple would make the result depend mostly on which table was unlucky and
when: the same method, run twice, would report wildly different scores, and
that variation would be larger than the difference between two methods. The
measurement would be destroyed by the thing it was trying to measure.

It would also throw away the evidence. A method that topples a glass on one
table in twenty and clears the other nineteen is a very different method
from one that topples on most tables, and the difference between them is
precisely what a reader wants. Carrying on is the same choice a test runner
makes when it reports every failing test instead of stopping at the first:
you learn more, and nothing has been forgiven.

**The table, though, is lost entirely.** A table where a glass went over
earns nothing at all — not even for the glasses that did end up with room.

This is where the rule earns its keep, and it is worth spelling out what the
alternative would be. If a toppled table still paid out for its other
glasses, then a hard, risky shove would be close to free: break one glass,
collect the rest, and come out ahead. A method could gamble its way up the
scorecard. By making the table worth nothing, and by counting the broken
glass in the run's own total, the examiner makes sure there is no table on
which breaking a glass pays. **There is no free breakage.**

The two kinds of bad ending are also reported on separate lines and never
added together. A table failed by a topple is never counted among the tables
merely left crowded. A cautious method that leaves glasses touching and a
reckless one that puts glass on the floor must not be able to look alike in
an average, because the project's whole ordering of outcomes says they are
not alike: a glass left alone is a result, and a glass broken is not.

## What the scorecard reports

Marking happens only after a solution has stopped, and it reads the
simulator's own record of where everything really is rather than anything
the solution reported. Each table produces one result, and the results are
added into one card per method. Every line on that card answers a question a
reader would otherwise have to ask.

**Glasses broken.** The thing that must not happen. It is counted in glasses
rather than in tables, so that a table where two went over is worse than a
table where one did.

**Tables separated with nothing broken.** The clean pass: every glass on the
table has room for the hand, and nothing fell. This is the headline, and it
is deliberately strict, because a table with one glass still crowded has not
been cleared.

**Tables failed by a topple**, kept apart from the next line for the reason
the last section gave.

**Tables left unfinished.** Nothing broken, and at least one glass still
crowded. Two quite different things end this way: the clock ran out, or the
solution declared itself done too soon. The card records which, because the
first is a solution that was too slow and the second is a solution whose
judgement was wrong, and they need different fixes.

**Glasses made pickable, out of all glasses.** The partial credit, which the
next paragraphs are about.

**Average arm time for a table that succeeded.** The cost of a win. It is
averaged over successful tables only, because a solution that gives up
early would otherwise look cheap, and the useful question is what a cleared
table costs rather than what an abandoned one costs.

**How often the solution declared itself done.** This measures whether a
solution has a stopping rule at all. A method that never says it is
finished spends every budget in full, and that fact should be visible on one
line rather than inferred from the others.

**Why credit is counted by glass and not only by table.** A table outcome is
one bit of information: cleared or not. If most tables are not cleared, then
every method scores near zero on that bit and the card cannot tell any of
them apart. A solution that leaves exactly one glass touching on every
single table and a solution that never moved the arm at all would both score
no cleared tables, and they are obviously not the same solution. Counting
glasses gives the card the resolution to say so, and to rank methods that
all fail the strict test. It is the difference between marking a paper on
whether every answer was right and marking it question by question.

Partial credit needs a baseline, because every table starts with one or two
glasses that already have room. A solution that does nothing therefore
scores above zero, and a count of pickable glasses at the end means little
on its own. So each table's result records how many glasses were pickable
at the start as well as at the end, and the honest reading of a method is
the gain between them.

Partial credit must also never reward a gamble, which is why it is
subordinate to the previous section: a table where a glass went over
contributes no pickable glasses at all, and the broken glass is still
counted. Resolution is worth having, but not at the price of making
breakage profitable.

**One run is not a measurement.** The last thing the card carries is the
spread across repeated runs, and that machinery is borrowed from problem 3
rather than rebuilt. Trained solutions are stochastic: asked the same
question twice they may act differently, because their action is drawn
rather than computed. Training varies with its own random seed as well, so
the same method trained twice gives two policies of different quality. That
variation can be larger than the gap between two methods, which means a
single run of each can report the wrong winner and give no sign that
anything was uncertain. A result quoted without a spread is not a result,
and a method that wins by less than its own spread has not been shown to
win.

**None of these numbers exists yet.** No table has been run by this
examiner. The first measured values will arrive with the solutions, and
until then any figure in this folder is a description of what will be
counted, never a result.

## Where to go next

- [The problem](problem.md) — what is on the table, what goes in, what must
  come out, and what "done" means here.
- [Problem 3's examiner](../03-push-glasses-apart/the-examiner.md) — the
  cell this one borrows, and the marking this one departs from.
- [Problem 3's problem statement](../03-push-glasses-apart/problem.md) — why
  the gap that matters is not the gap between the glasses, and why a pushed
  glass slides or tips.
- [The cell](../the-cell.md) — the arm, the table, the glasses and the
  gripper, described once for the whole project.
- [Known gaps](../known-gaps.md) — the limits this project knows it has,
  including the one behind "pickable".
