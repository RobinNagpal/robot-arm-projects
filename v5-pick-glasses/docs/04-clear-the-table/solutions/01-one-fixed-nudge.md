# Solution 1 — one fixed nudge, with no view of the whole table

> **What it uses** — arithmetic, and nothing else. There is no model, no
> weights file, no training set and no licence condition. Not one number in it
> was fitted to anything.
> **What it does** — It drives the arm round the table and looks from every
> side, because the camera rides on the arm and sees only what is in front of
> the hand. It merges those looks into one picture of the table. It picks the
> glass with the least room and pushes it straight away from whatever crowds
> it. Then it looks again. When it can think of no further push worth making,
> it drives round the table once more to check, and says it has finished.
> **What it costs** — No data and no training time, because nothing learns. No
> hardware to rent, because a decision is a few hundred sums. The only cost is
> the arm's own time, and this solution spends more of it on looking than on
> pushing.
> **The cell is described once, in [the cell](../../the-cell.md)** — the arm,
> the table, the glasses and the hand. What follows is only what belongs to
> this solution.

## Introduction

This is the plainest possible answer to [problem 4](../problem.md), and it is
the one every other answer is measured against.

Problem 4 asks the arm to clear a crowded table on its own. Some glasses stand
too close together for the open hand to get round them, so the arm has to drag
them apart until each one has room, and then say for itself that the table is
finished. It is [problem 3](../../03-push-glasses-apart/problem.md)'s task with
two helps removed. The camera above the table is gone, so the arm carries its
own camera and can only see the patch of table in front of its hand. The
push-by-push hand-over is gone, so nothing counts the pushes and nothing tells
the arm when to stop.

This solution answers that question with no learning of any kind. It borrows
the part of problem 3's first solution that chooses a push, and it writes the
parts that the overhead camera used to make unnecessary: where to stand to see
the table, how to remember what has been seen, and how to decide that there is
nothing left to do.

It exists to be the floor. Every other solution to problem 4 pays for its
answers with recorded demonstrations, with training runs, or with a borrowed
model and its licence, and a price only means something next to something that
costs nothing. **A solution that cannot beat this one has earned nothing.**

By the end of this page you will know what the solution does, why each part of
it is there, what it scored on the tables it is judged on, why that score has
no spread, and where it is strong and where it breaks.

**No glass's size appears below.** This project never writes a glass's
dimensions down, because the arm is supposed to measure every glass during the
run. The numbers quoted here belong to the hand, to the cell, or to a results
file.

## What question it answers

The question is **how much of problem 4 is answered by careful geometry
alone.**

That matters because problem 4 changes two things at once, and it is easy to
blame the wrong one. When a trained policy does badly here, the reason might be
the training, or it might be that the task is simply harder now that looking
costs time and nobody says when to stop. A solution with nothing fitted in it
cannot be failing for the first reason, so whatever it scores is a measurement
of the second. Everything above its score is what the learning bought.

## What it does, from the top down

The whole solution is one loop, and the loop has six steps. Each step exists
because of the one before it, so they are easiest to read in order.

**First, it sweeps.** It walks a ring of **stands** and looks from each one. A
stand is a pose the arm can hold at travel height, just off the edge of the
zone the glasses stand in, facing across it. There are eight of them on this
cell, one for each direction the arm can reach from, and walking all eight
costs about eight seconds of arm time.

It looks from every side rather than from the fewest sides that would cover the
table, and the reason is **occlusion**: a glass standing behind a nearer one is
not in the picture, however well the camera frames the table underneath it.
Which glass hides which depends on where the glasses happen to stand, and no
tour worked out from the shape of the cell alone can know that. Looking from
every side is the general cure, because two glasses that line up from one
direction do not line up from another. The sweep is therefore bought for the
*last* glass rather than the first — and the last glass is exactly the one that
would otherwise be declared finished without ever being seen.

**Second, it remembers.** Each look is folded into one picture of the table,
which this page will call the arm's **belief**. Two readings of the same glass
are averaged together, because every look carries its own measurement error and
averaging two noisy readings gives a better one. A glass that has just been
pushed is forgotten before anything else, so that a reading taken after the
shove is never averaged with readings of where the glass used to stand.

This step is new to problem 4 and it is the deepest change in it. Problem 3
handed over the whole table on every call, so the arrangement was an input.
Here the arrangement is something the solution has to build up and keep,
because no single look contains it.

**Third, it decides.** Problem 3's chooser is handed the belief and names one
push: the shortest push that gives some glass room, taken as low as the hand
can reach. A glass that already has room is held back from the chooser first.
Problem 3 never needed that, because its cell lifted a glass onto a rack the
moment it had room and so the chooser never saw one; nothing is lifted here, so
without holding them back the chooser would nudge a glass that needed nothing,
over and over, until the clock stopped.

**Fourth, it finds the glass before it pushes it.** This is where problem 4
costs the most, and the cost is not avoidable.

Problem 3 puts the fingertips down a little outside the glass and then creeps
forward until a force sensor feels the glass, pushing only from there. That
allowance is needed, because the hand meets a glass at the hand's own height,
where the glass can be much narrower than at its widest point. Problem 4 hands
over a whole short path at a time, and a path cannot creep. So the distance has
to be *measured*, and the only sense left for measuring it is the camera.

That turns problem 3's one test push into two. The first is a **ranging push**:
drive the fingertips a few millimetres deeper than last time and look. It says
only whether the glass has been met, not whether it slides. The second is the
**test push**, which is problem 3's experiment unchanged: now that the distance
is known, push the glass a short fixed distance and look at whether it kept up
with the fingertips. Every later push of that glass is written from the
measured distance, so the glass lands where the chooser aimed instead of short
of it.

How deep the ranging may go is bounded, and the bound is the whole safety of
the step. **A camera cannot tell "not touched yet" from "touched, and
leaning"**, because the glass stays still either way, and a force sensor is
what told problem 3 the two apart. So every millimetre deeper has to be treated
as a millimetre of lean, and the solution stops at the lean that problem 3's
own guard already allows. Reaching deeper than that is how a glass ends up on
its side.

**Fifth, it looks again, from one side only.** A push is carried out without
anything watching it, so the glass has to be measured afresh — from the one
stand it should be least hidden from, worked out from the belief. One stand and
not the ring, because the ring is the price of making a claim about the whole
table, and no such claim is being made yet.

**Sixth, it says it has finished.** When the chooser has no push left that it
is willing to make, the arm walks the whole ring once more and asks again. Only
then is the table declared finished. Running out of arm time is never reported
as "done", because that ending belongs to the clock, and a solution that called
it "done" would be claiming it knew when to stop.

## How it is marked

[The examiner](../the-examiner.md) owns the marking, and three of its rules
decide how the numbers below should be read.

**The budget is the arm's own seconds, and it belongs to a queue of tables
rather than to one table.** Every solution is offered the same fifty tables in
the same order, with fifteen arm minutes for all of them together, and each
table may spend as much of what is left as it needs. So speed is part of the
score instead of a column beside it: a solution that clears a table beautifully
in four minutes reaches fewer tables than one that clears it roughly in one.
Looking costs arm time exactly as pushing does, because the camera has to be
carried to where it can see.

**Near the end of a queue a table can be offered and handed straight back**,
because what is left of the clock cannot pay for even the first path. The arm
never moves, and such a table is not counted at all — counting it would claim
the solution got further down the queue than it did, and would put every glass
on it into the score as a glass left crowded.

**A glass is pickable when it is standing, inside the glass zone, and has room
for the open hand.** It is read from the simulator after the run rather than
from anything the solution reported, and a table that lost a glass earns
nothing at all, not even for the glasses on it that did end up with room. That
last rule is what stops a risky shove from paying.

## What it scored

The tables numbered below ten thousand are for building and choosing on, and
this solution's own folder reports what it costs on twenty of them. **The
tables from ten thousand upwards are the measurement**, and they are walked
once and never tuned against. The queue is fifty of them, offered in order, and
it is deliberately longer than any solution can finish, so that a solution runs
out of time rather than out of tables.

| | |
|---|---|
| Tables attempted | **26** of the fifty offered |
| Glasses on them | 102 |
| Tables separated, with nothing broken | **10** |
| Tables failed by a glass going over | **0** |
| Tables left crowded | 16 |
| Glasses broken | **0** |
| Glasses pickable | 39 at the start, **64** at the end |
| Glasses it freed | **25** |
| It said it had finished | on 24 tables; the clock stopped the other 2 |
| Said it had finished while the table was still crowded | 14 |
| Paths the cell's safety interlock refused | 0 |
| Arm time spent | almost exactly the 900 seconds given |
| Arm time for a table it separated | **43.6 s** |

Four of these are worth reading slowly.

**Ten tables of twenty-six were cleared completely**, meaning every glass on
them ended standing with room for the hand. That is the strict test, and it is
strict on purpose: a table with one glass still crowded has not been cleared.

**Nothing was broken, and the cell never had to stop it.** Over 813 answers the
interlock — the cell's refusal to drive the hand into a glass the physics says
would tip rather than slide — was never once needed. So the caution is the
solution's own and not the cell's, which matters because a solution that leans
on the cell to save it from itself is not the same as one that never needed
saving.

**Fourteen tables were declared finished while still crowded.** This is not the
solution mistaking a crowded table for a clear one. Its stopping rule fires
when the chooser has no push left that it is willing to make, and it sweeps the
whole ring again before saying so. What the fourteen record is glasses the
geometry would not touch, not glasses it failed to notice.

**Five of the twenty-six tables cost one sweep and nothing else** — about eight
seconds and nine answers each — because the chooser found nothing it would push
and the solution said so after checking. A table that is refused quickly is
cheap, and cheapness in a queue budget is worth something: it leaves the time
for the next table.

## Why the score has no spread

[The examiner](../the-examiner.md#what-the-scorecard-reports) asks every
solution to walk the queue three times, because one run of a solution that
draws its answers is not a measurement. This solution was walked three times
too, and **every count above is identical on all three walks** — not close, but
identical, table by table, down to the hundredth of an arm second and the exact
number of answers.

So there is no spread to report, and reporting one as "± 0" would be the wrong
statement: it would suggest a variation that was measured and came out at zero,
where the truth is that this solution has nothing to vary. Given a table it
always answers the same way. The push is computed from the measurements, the
ranging and test pushes are fixed lengths, the ring is walked in a fixed order,
and no number anywhere in it is drawn at random. The only figure with any
movement in it is the laptop time spent thinking, which wobbles by a fifth of a
second over about twelve, and that is a fact about the computer rather than
about the method.

**This is not true of the solutions that learn**, and that is why the examiner
asks for the repeats at all. A policy of the modern sort draws its action from
a distribution rather than computing it, so asked the same question twice it
may act differently. Its training has a random seed of its own as well, so the
same method trained twice gives two policies of different quality. That
variation can be larger than the gap between two methods, which means a single
walk of the queue can report the wrong winner and give no sign that anything
was uncertain. For this solution the three walks are a check that the
measurement reproduces. For a trained one they are the measurement.

## Where it is strong and where it breaks

The strengths and the weaknesses come from the same place: how little the
method claims.

**It cannot be wrong about pushing, because it says nothing about it.** It
claims a direction, which no friction can reverse, and it keeps the distance
small on purpose and repeats. Nothing in it predicts where a glass will land,
so nothing in it can be wrong about that.

**Every refusal has a reason that can be checked with a ruler.** There is no
step whose output cannot be printed and argued with.

**It spends more of the budget on looking than on pushing.** On the tuning
tables rather more than half the arm time went on moving the camera, and the
sweeps are most of that. This is the honest price of taking the overhead camera
away, and it is the number later solutions have the most room to improve.

**It has only one heading.** The chooser pushes a glass straight away from
whatever crowds it, so when that one approach is blocked — and in a tight group
the blocking neighbour stands exactly where the hand would have to come in — it
has nothing else to try.

**It cannot help a glass crowded from two sides.** Pushing it away from one
neighbour pushes it towards the other, and the loop can swing between them.

**It refuses rather than reaching when the camera cannot tell it enough.** The
ambiguity between "not touched" and "touched and leaning" has to be resolved
somehow, and every resolution costs something: reaching deeper topples the
leaning glasses, and refusing leaves standing the glasses that are narrow at
the hand's height. This solution reaches as far as problem 3's lean guard
allows and then refuses. **It is the safe way to be wrong**, and it is the
direction this whole project is deliberately wrong in: a refused glass is a
result, and a broken glass is not.

## Where it sits beside the others

**Against [the ranked chooser](02-geometry-ranked.md)** the difference is a
search and a fitted model. That solution enumerates every legal push instead of
taking the first one the printed rule names, and sorts them with trees fitted
in problem 3. It is the same loop otherwise, with one method replaced, so the
pair isolates the choosing. On the held-out queue it separates seven tables
where this one separates ten, and its own page works out where the difference
comes from.

**Against the solutions that are trained here, or borrowed and fine-tuned
here**, the difference is everything fitted, and this solution is the number
they have to clear. They buy a shorter loop: a policy that emits a good push
straight away does not need the ranging push, the test push or the repetition.
What they must not buy is a broken glass, and the zero in this solution's
broken column is the bar.

---

← [Problem 4 — clear the table](../problem.md) ·
[The examiner](../the-examiner.md) ·
[Solution 2 — geometry generates, a model ranks](02-geometry-ranked.md) →
