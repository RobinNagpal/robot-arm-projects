# Problem 4 — clear the table

## Introduction

Problem 4 asks the arm to do what [problem 3](../03-push-glasses-apart/problem.md)
asked: a table holds drinking glasses, some of them standing too close together
for the gripper to get round one without fouling its neighbour, and the arm has
to drag them apart across the table until every glass can be picked up. The
task is the same task. What changes is **who is in charge of the run, and how
much of the table the arm can see at once**.

In problem 3 the arm could see the whole table whenever it liked, from a camera
bolted above it, and a shared program decided when a table was finished. In
problem 4 the camera is carried by the arm, so the arm has to move in order to
look, and the solution itself has to say when the table is finished. Both of
those were conveniences, and this problem takes them away.

By the end of this document you will understand which two assumptions problem 3
was allowed and this one is not, what is on the table, what the arm is given
and what it must hand back, why the budget is measured in the arm's own seconds
rather than in the computer's, what happens when a glass goes over, and what is
counted when the arm stops. **Nothing here has been measured yet.** The
measurement is being built, and this document describes the question rather
than any answer to it.

## Why there is a problem 4 at all

This project is a ladder, and the rule of the ladder is that **each problem is
the one before it with an assumption removed.** Problem 1 has one glass on a
bare table, so nothing hides anything. Problem 2 puts several glasses of one
kind on the table and takes away the free choice of viewpoint. Problem 3 starts
from problem 2's answer and takes away lifting, so the only way to move a glass
is to drag it. Each step leaves the task alone and removes a comfort, because
that is how you find out which comfort the earlier answer was leaning on.

Problem 4 removes two comforts, and they are both comforts of the
**measurement** rather than of the task. This matters, because it is the
easiest thing to misread about this problem. Problem 4 is not a second
scorecard bolted onto problem 3 to produce friendlier numbers. It is the next
rung of the same ladder, and the two assumptions it removes are these.

**Problem 3 was allowed a camera above the table.** Its examiner rendered the
whole glass zone from a camera fixed above the middle of it, looking straight
down, and any solution could ask for that picture at any moment for nothing.
Problem 4 is not allowed it. The camera is mounted on the arm, so the arm sees
only what is in front of it, and the only way to see somewhere else is to go
there.

**Problem 3 was allowed a push-by-push hand-over.** Its solutions handed over
one push, or one short run of waypoints, and the shared machinery around them
did three things on their behalf: it decided when the table was finished, it
threw away answers it judged pointless before carrying them out, and it
budgeted in pushes. Problem 4 is not allowed any of the three. A solution runs
continuously, declares itself finished, has every answer carried out as given,
and is charged in arm time.

Neither of those is a complaint about problem 3. Its arrangement holds
everything still except the one thing being studied, which is exactly what is
needed to answer a question of the form "what did this one change do?", and the
[committed results](../../03-push-glasses-apart/results/README.md) are readable
because of it. Problem 3's scorecard stays, and stays the instrument for that
kind of question. Problem 4 asks the other question: **what would this arm do
if nobody were helping it?**

## What "clear the table" means here, and what it does not

The name needs pinning down at once, because it is easy to read it as emptying
the table. It is not that. **No glass is lifted and no glass is racked in
problem 4.** The run ends with every glass still standing on the table, and the
question asked of that final arrangement is whether each glass now has room
around it for the gripper to close on.

So what is cleared is the **crowding**, not the table. Lifting a glass belongs
to problem 1, and problem 3 borrowed it as a free action so that it could count
glasses racked; here it is not borrowed at all, because the answer is visible
in the arrangement itself.

"Room" is the same quantity problem 3 defines, and
[its problem document](../03-push-glasses-apart/problem.md) derives it in full.
In short: to close on a glass, the open hand has to be around it, so what the
glass needs is not daylight between it and its neighbour but **76 mm of clear
room measured from its middle to the neighbour's nearest edge.** Because the
test measures to the neighbour's edge rather than to its middle, it is not
symmetric: a narrow glass standing beside a wide one is crowded before the wide
one is, since the wide one's rim reaches further into the gap. A method that
compares distances between middles will get that case wrong, and it will get it
wrong in the direction that calls a pair fine when the hand does not fit.

## What is on the table

Each table holds **four to seven glasses**, and the arrangement is built to
contain three different situations at once:

- at least one **touching pair**, so there is crowding that plainly has to be
  dealt with;
- at least one **touching group of three**, because a crowd of three cannot be
  fixed by one push and forces a solution to think about order;
- **one or two glasses that already have room**, so that "this one needs
  nothing from me" stays a decision the scorecard can see.

The number of crowded glasses is kept inside a narrow band. This is a
statistical convenience rather than a rule about glasses: when tables resemble
each other, a difference between two solutions stands out against fewer tables,
so fewer runs are needed before the difference can be believed.

**The composition must still vary from table to table, and that limit is the
important half of the draw.** If every table held exactly five glasses as one
pair and one triple, then that shape would be a constant, and a constant is
something a trained policy can memorise instead of learning to separate
glasses. Such a policy would score well here and badly on the first real tray
it met, and nothing in the score would warn anyone. So the count varies, and so
does how the crowding is distributed, while the band keeps the variation from
swamping the comparison.

Memorising is also why the tables are **numbered and the numbers split**. Each
table is drawn from a single number, so the same number always gives back the
same table and any solution can be run on exactly the tables another was run
on. A high range of numbers is then kept for measuring, and nothing whatever is
chosen on it: the methods, their settings, and the size of the time budget are
all chosen on tables drawn the same way from below that range. The budget
deserves saying out loud, because it is the easiest one to forget — a budget
tuned by watching the tables it will be scored on is a budget selected to
produce a result.

One more condition is checked before a table is accepted. Every crowded glass
on it must be one the physics can **slide rather than tip**, which is checked
with the same arithmetic problem 3's simplest written-rule solution uses: the
glass's measured base width, the height the jaw pushes at, and the friction
range the project is willing to believe. A glass that tips before it slides can
only honestly be refused, so a table containing one would measure the draw
rather than the solutions; such a table is redrawn until every crowded glass on
it can be moved.

## What goes in: one look, from a camera the arm carries

At every moment the arm knows four things, and they are the whole input: the
picture its own camera can see from where the jaw is standing, the glasses that
fall inside that picture measured as problem 3 measures them, where the jaw
itself is, and how much arm time is left.

**There is no call that hands over the whole table.** That single absence is
the difference between this problem and problem 3. A solution that wants to
know what is standing in the far corner has to take the arm to where the corner
is in shot, and the journey costs it part of its budget.

The measurements themselves are unchanged, and deliberately so. Each reading of
a glass carries problem 2's measured error, drawn from the table's number and
the number of the look, so looking twice is worth something and the first look
at a given table is identical for every solution. Problem 4 narrows what the
arm is shown; it does not make the numbers noisier. If it did, a difference
between the two problems could not be attributed to the camera moving.

### Why the camera belongs on the arm

A camera bolted over the work area is a convenience of the simulator. A real
cell puts the camera on the wrist, for two reasons. It is what can be
installed, calibrated and replaced on a real robot, and a fixed overhead camera
stops working the moment somebody moves the table or stands in front of it. So
the overhead view is not a mild simplification; it is an arrangement that does
not exist in the place this project is pretending to be.

Moving the camera also makes **looking cost something**, which is correct. With
a camera above the table, seeing everything is free, so a solution that looks
carefully and a solution that never looks pay the same. With the camera on the
arm, looking is a motion like any other, so a careful solution spends part of
its budget on care. That trade is a real part of the job, and the arm-time
budget measures it without anybody having to invent a penalty.

### Why the two changes only make sense together

A moving camera is only useful if the solution can still change its mind. Under
problem 3's hand-over a solution commits to a whole run of waypoints from its
ready pose, and at that moment the wrist is nowhere near the glass it is about
to touch, so a close view of that glass would arrive after the decision that
needed it. Running continuously — look, act a little, look again — is the only
arrangement in which a close view arrives in time to be acted on. That is why
the camera and the open run are one problem and not two.

It is worth being plain about what is expected from this, because problem 3 has
already run the strongest version of the neighbouring experiment. Its imitation
policy was given exact numeric readings on top of its picture, which is far
more information than a different camera angle provides, and the pushes blocked
on the way down went from 366.3 to 370.3 — no change at all. The
[committed analysis](../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md)
explains why: the binding constraint was the straight drop onto a named point,
not the information used to name it. **So the reason to expect something here
is timing rather than detail.** A view that arrives while the jaw is descending
can still stop the descent; a view taken before the path was chosen cannot.

## What must come out

A solution answers each look with one of exactly two things.

**A path for the jaw**, written as waypoints in the same numbers problem 3's
bench already accepts, and carried out by the same machinery in the same
physics. A path that pushes a glass and a path that only carries the camera
somewhere useful are the same kind of answer, because the camera rides on the
arm; there is no separate "look" action to be had for free.

**Or the statement that the table needs nothing more.** The solution may give a
reason with it, for the record, and the reason is never scored. It is worth
recording anyway, because a table left crowded on purpose and a table left
crowded by mistake read identically in the numbers.

### Why saying "done" is part of the answer

Nothing else decides when a table is finished. A solution that never says it is
finished spends its whole budget and is marked as unfinished; a solution that
says it too early is marked on the table it left crowded. Knowing that a job is
done is part of the skill, so it is part of what is measured, and problem 3's
own results show what happens when it is not. Its borrowed foundation model, run
as it downloads, racked 48 glasses, which were **exactly** the 48 that already
had room at the start: its own pushes achieved nothing, because its jaw came
down about 200 mm above the table. The loop ended each of its tables for it when
every glass had been refused or had spent its pushes, so a policy that could
not tell a finished table from an untouched one was never charged for the
difference. Here it would be.

### What the cell still does, and what it stops doing

The cell keeps its **tipping interlock**. A real cell keeps its safety
interlocks, and this one is arithmetic on measurements the arm already has: a
push at height `h` on a glass whose base is `2a` across, on a table it rubs
against with friction `μ`, slides the glass while `h < a / μ` and tips it above
that. So the cell will not drive the jaw into a glass the physics says would go
over rather than slide, and it records how often it had to stop one.

What the cell **stops** doing is working on the solution's behalf. It no longer
counts pushes, and it no longer throws away an answer because it judges the
answer pointless. That second habit flattered some solutions and not others,
and problem 3 measured by how much: its fine-tuned model had 421 of its 1,515
answers discarded for aiming at a glass the loop had already refused, against 5
of 1,855 for the same model unfitted. A solution that aims badly therefore
looked safer than it was, because a shared protection was catching its mistakes
before they reached the table. In problem 4 every answer that the interlock
permits is carried out as given.

## The budget is the arm's own time, not the computer's

Problem 3 charged a run in pushes. That hides something, because a path that
sweeps the jaw right across the glass zone and a path that nudges a glass a few
centimetres each count as one push, although the arm spends several times
longer on the first. Counting pushes therefore rewards doing the same amount of
work in fewer, larger motions, which is not what anybody wants from a robot.

So the budget is **simulated seconds of arm motion**. It is a sum rather than a
measurement: the bench spends on each leg of a path either the fixed period it
puts between waypoints or the time the jaw needs to cover that leg at its top
speed, whichever is longer, so the seconds a path costs follow from the path's
own geometry. Two consequences matter. The figure is identical on any
machine, because no real clock is involved. And looking costs arm time through
the same arithmetic, because moving to see is moving.

**Thinking time is recorded, but in its own column.** It is the solution's own
compute, and it is not part of the budget, because a budget that mixed the two
would compare laptops and rented graphics cards rather than methods. Problem 3
learned that the hard way: the same runs timed while other work was on the
machine reported up to three and a half times the thinking time, so a compute
figure measured under load measures the load. Keeping the two columns apart lets
a reader see both what a method costs the robot and what it costs the computer,
and decide for themselves.

## What happens when a glass goes over

**A toppled glass fails that table, and the run carries on to the next one.**

It does not fail the whole run. Failing the whole run would let one bad instant
erase everything a solution did on the tables after it, so the score would
report a method's worst moment instead of its behaviour, and two methods that
topple one glass each would be indistinguishable however differently they
handled every other table in the set.

**There is also no free breakage.** Allowing one topple a run before the
counting starts would be worse than failing the whole run, because it makes
gambling free: a method could take its most dangerous attempt first and pay
nothing for losing. This project's standing rule is that **a refused glass is a
result and not a failure**, and that rule exists precisely so that nothing is
ever encouraged to gamble with a glass. A free breakage would undo it.

Room for error comes from somewhere else, which is the **spread across runs**.
Anything learned is trained several times and anything stochastic is run several
times, and the scorecard carries the spread beside the middle value, so a
method that wins by less than its own spread has not been shown to win. Being
forgiving inside one run and being honest about variation between runs are
different things, and only the second is sound.

## How a table is marked

The arm stops, and the arrangement in front of it is what is marked. Every
table ends in exactly one of three states, and the three are kept apart because
they mean different things.

**Separated.** Every glass on the table has room, and nothing was broken. This
is the only clean pass.

**Failed.** A glass went over. This is unrecoverable rather than merely
unsuccessful, because broken glass leaves shards and an arm that will carry on
moving through them.

**Unfinished.** Nothing was broken and the table is still crowded, either
because the solution said it was done too early or because the clock stopped
it. An unfinished table is not a failed one, and lumping the two together would
hide the most useful distinction on the scorecard: between a method that is too
slow or too cautious and a method that is dangerous.

Over a set of tables, these are reported:

| what is reported | why it is there |
|---|---|
| glasses broken | safety, which is never traded against speed |
| tables separated with nothing broken | the headline score |
| tables failed by a topple | the failures that cannot be undone |
| tables left unfinished when the clock stopped | slow or cautious, which is not the same as dangerous |
| glasses made pickable, out of all glasses | partial credit, which is where the resolution comes from |
| average arm time for a table that succeeded | speed, taken only from real successes |
| how often the solution declared itself done | whether it knows when to stop |

### Why counting glasses matters as much as counting tables

The glass count is easy to dismiss as a softer version of the table count, and
it is not. Consider two solutions on a set of tables: one leaves a single glass
touching on every table, and one never moves at all. **Both separate zero
tables**, so the headline score calls them equal, and they are plainly not
equal — the first is one push from succeeding everywhere and the second has
done nothing. The glass count separates them, and it does so on every table
rather than only on the ones that were nearly finished.

This is the same reason a test suite reports how many assertions passed rather
than only whether the suite passed. A single pass-or-fail bit per table throws
away almost everything the run found out, and with four to seven glasses a
table there is a lot to throw away. The table count is still the headline,
because a table with one crowded glass left is a table the next stage cannot
use; the glass count is what gives the comparison its resolution.

### Why no glass's size is written down

Whether a glass is **pickable** is computed during the run, from the gripper's
own numbers and the glass's **measured** width, exactly as everywhere else in
this project. No glass's size appears in the bench, in a constant, in a test, or
in this document.

That is the project's first rule, and it is not bookkeeping. The whole point of
the exercise is an arm that meets a glass it has never seen, so a measurement
written down anywhere is a measurement the arm did not have to take, and a rule
that leans on one is a rule that will fail on the first unfamiliar glass. The
scorecard obeys the same rule as the solutions do: it asks whether the hand fits
round what was measured, not whether the glass matches something known.

## What is deliberately not in this problem

**Lifting, and racking.** No glass leaves the table. Problem 3 borrowed a free
pick so that it could count glasses racked; here the final arrangement is the
answer.

**Telling one glass from another over time.** The glasses are still one known
kind, and a solution that merges what it saw across several looks may use the
bench's own identifiers for now. Deciding that the glass in this picture is the
glass from the last picture is the association problem, and it belongs to
problem 2.

**Any relaxation of the cell's safety rules.** Nothing about the physics, the
glasses, the hand or the tipping arithmetic is softened for this problem; the
cell is imported from problem 3 rather than copied, so the two cannot drift
apart.

**A new comparison of methods.** Problem 4 is a question, and the methods that
will answer it are problem 3's seven. Each will be run again here, under this
scorecard, on these tables.

## What has been measured

Nothing yet. The draw, the arm's clock, the camera on the wrist, the open run
and the scorecard are being built in
[`04-clear-the-table/bench/`](../../04-clear-the-table/bench/), and the
geometry reference is being ported to this problem's contract so that there is
a solution to check the bench against. Until those exist and have been run,
this folder holds no result at all, and no number in it should be read as one.

When results do arrive they will sit beside problem 3's, because the two
scorecards answer different questions and both are worth keeping: problem 3's
says what one change did, and problem 4's says what the arm would do on its
own.

## Where to go next

- [The examiner](the-examiner.md) — the tables, what a solution is given and
  never given, the arm's clock, and how a run is marked.
- [Problem 3's problem](../03-push-glasses-apart/problem.md) — why dragging
  rather than lifting, the three distances that matter, and the height limit
  that decides whether a glass slides or tips.
- [Problem 3's examiner](../03-push-glasses-apart/the-examiner.md) — the
  per-push arrangement this problem takes two things away from.
- [The cell](../the-cell.md) — the room, the arm, the glass zone and the
  vocabulary every problem here shares.
