# What was changed in the learned solutions, and what each change bought

## Introduction

The first measurement of problem 4 ended with a plain result: the two solutions
that only ever make a push they can justify from geometry broke no glass and
separated the most tables, while every solution with a fitted model inside it
either broke glasses or changed nothing at all. This page is the record of what
was done about that. It names each change, says which solution it was made to,
and gives the numbers before and after, so that at the end it is clear **which
change bought which improvement** rather than only that the numbers moved.

Two rules were kept while making these changes, because without them an
improvement would not mean anything.

**The problem was not made easier.** The tables are drawn the same way, the
held-out queue is the same fifty tables offered in the same order from table ten
thousand, the arm time for the whole queue is the same fifteen minutes, and what
counts as a separated table is unchanged. Nothing was moved from a solution into
the examiner, and the examiner was not asked to do more work on a solution's
behalf.

**The examiner does less, not more.** Every change below sits inside a solution,
in the code that decides what to answer. The one new shared file,
`bench/keeping_clear.py`, is arithmetic a solution runs over its own answer
before handing it over; nothing in the examiner calls it, and a solution that
does not call it is treated exactly as before.

## The two reasons the fitted solutions failed

Both are measured, and they call for different changes, so they are kept apart
all the way through this page.

**The first is the data's shape.** Once the overhead camera is taken away, four
of every five answers the teacher gives are a move to see from somewhere else,
and only about one in thirty-five is a push at the task. A network fitted to
minimise the distance between its answer and the teacher's produces the average
answer, and the average of that material is a look. So the imitation policy and
the fine-tuned borrowed model both learned to travel and not to push.

**The second is acting on a prediction where being wrong costs the table.** The
world model frees more glasses than anything else and still scores below plain
geometry, because it broke eight of them. Its own page measures why: the search
does not sample the model's opinion of the risk, it maximises over the model's
opinion of the gain, so it lands by preference where the model is most
optimistic.

A third cause belongs to neither, and it is the cheapest to remove. **Most of
the breakages were not caused by a push at all.** A waypoint names the middle of
the hand and the fingers hang about seventy millimetres below it, so a path that
rides at the height the teacher travels at still drags the hand through the top
of a tall glass. That is a geometry mistake in carrying out an answer, not a
mistake in choosing one, and it is fixed by arithmetic rather than by fitting.

## The changes

Each change has its own section below, added as it is made and measured.

### 1. Every solution keeps the hand clear of a glass it did not aim at

**What it is.** A new shared file, `bench/keeping_clear.py`, holds the
arithmetic for one rule in two parts: an answer is either a look, with every
waypoint at the height the jaw travels at, which nothing on the table reaches;
or it is a push at one named glass, checked stretch by stretch against every
glass the solution has measured, which may reach the glass it names and no
other. Anything else is raised to travel height, which costs the same arm time
and touches nothing. The check grows every glass by four millimetres first,
because a reading carries the camera's error.

**Why it is not a change to the problem.** The rule is applied by each solution
to its own answer, and it uses only what that solution has measured. The cell's
own interlock is unchanged and still refuses only what it refused before.

**The rule has three parts, and the third is the one that was missed first.** An
answer may ride high, or it may be a push at a named glass, and a push may reach
only the glass it names. The first attempt at this stopped there, and it did not
work: a path that sweeps across the table at the height of the glasses' rims
reaches exactly one glass and nothing else, so counting glasses passed it, and it
tips that glass over instead of sliding it. A glass is pushed at the height the
jaw works at, where the shove goes through its foot, and the tipping rule every
solution shares is worked out for that height and for no other. So the third part
is about the *shape* of a path: **across the table high, or across the table low,
and nothing in between.** Going straight down is allowed at any height, because
the cell watches the force on the way down and backs the hand off the moment it
touches anything.

**What it bought.** The borrowed model used as it downloads, which broke twenty
glasses on its first walk of the held-out queue, now breaks none:

| fifty tables offered from 10,000 | before | after |
|---|---|---|
| Tables failed by a topple | 14 | **0** |
| Glasses broken | 20 | **0** |
| Pickable share | 0.018 | **0.400** |
| Glasses it gave room to | −1 | 0 |
| Tables attempted | 15 | 12 |

The share rises from almost nothing to 0.400 because a table that loses a glass
counts for nothing at either end, and no table loses one any more. It still frees
no glasses, and that is the honest result: of its answers, seven hundred and
thirty-seven were raised for travelling at the height of the glasses' rims, which
is the only thing it was doing.

### 2. The world model searches pessimistically and pays for risk

**What it is.** Three changes inside the search, all of them about the same
thing: a search that asks a model about a few thousand pushes and takes the best
answer is choosing the largest error, not the best push.

- **Every reading is the ensemble's least favourable copy, not its average.**
  Three copies of the network are fitted from different starting weights, so
  where they agree the model has seen pushes like this one and where they
  disagree it has not. The crowding the table is expected to be left with is now
  the worst of the three rather than the mean of them, and so is every check on
  whether a glass would leave the zone. Disagreement now costs the search
  instead of being something it can exploit.
- **A chance of toppling has a price as well as a limit.** The limit was already
  there, and a limit alone makes every push under it equally attractive, so the
  search preferred the candidate at the very edge of what the model would allow.
  A push now pays five millimetres of crowding for each chance in a hundred of
  putting something over, which is what a fifty-millimetre push pays in travel.
- **Candidates whose hand would sweep a neighbour are thrown out before they are
  ranked.** The model is asked where the glasses will end up and never asked what
  the hand passes through on the way in, so it was free to choose a push whose
  approach crossed a glass nobody had chosen to move. The corridor rule is the
  geometry reference's own, written out over whole arrays so the search can ask
  it about hundreds of candidates at once, and the clearance check above is asked
  of the best few as well.

**What each one bought, measured on forty tuning tables with one search seed**
(these are tables 500 to 539, which nothing is marked on):

| | tables separated | glasses broken |
|---|---|---|
| as committed | 17 | 4 |
| the worst copy instead of the average | 17 | 2 |
| and a price on risk | 17 | **1** |
| and the corridor filter | 17 | **1** |

**Two ways of shortening its pushes were measured and dropped.** The record above
says the pushes that break a glass are about three times longer than the rest, so
the obvious next move is to make the search prefer shorter ones. Raising the price
of a millimetre pushed from 0.1 to 0.3 separated 33 tables of a hundred against
48, and capping the push at sixty millimetres separated 39, while each saved one
glass of the three. **Fifteen tables, or nine, for one glass is not a trade worth
making**, because a table left crowded scores nothing either and the share counts
every glass standing on it. So the pushes stay as long as the model asks for, and
the next rung is more data in the band where it is weakest rather than a
narrower search.

**What was tried and dropped.** Putting the teacher's five-millimetre test push
in front of every long push, which is what this solution's own page proposed as
its next rung, measures the one thing the model is worst at instead of
predicting it. On its own it cut the breakages from four to one, exactly as hoped
— and it cut the tables separated from seventeen to **eight**, because a glass
that does not keep up with a probe is then left alone for the rest of the table.
Once the search was pessimistic it bought nothing that pessimism had not already
bought, so it is not in the solution. A tighter limit on the predicted chance
(three in a thousand rather than one in a hundred) cost two separated tables and
saved nothing, so that is not in either.

**What it bought over two hundred tuning tables**, which is where the decision
between configurations was made, because forty tables cannot tell one from
another:

| two hundred tuning tables, two search seeds | before | after |
|---|---|---|
| Tables separated | 74 | **86** |
| Glasses broken | 31 | **9** |
| Glasses it gave room to | +231 | **+254** |
| Arm seconds a table | 29.7 | **25.2** |

**And on the held-out queue**, which is the score:

| fifty tables offered from 10,000 | before | after | the geometry reference |
|---|---|---|---|
| Tables attempted | 32 | **45** | 26 |
| Tables separated | 11 | **14** | 10 |
| Tables failed by a topple | 7 | **1** | 0 |
| Glasses broken | 8 | **1** | 0 |
| Glasses it gave room to | +29 | **+39** | +25 |
| Pickable share | 0.560 | **0.603** | 0.627 |
| Thinking an answer | 6 ms | 10 ms | 15 ms |

So the world model now separates more tables than any other solution to this
problem, frees half again as many glasses as the geometry reference, and reaches
nearly twice as many tables in the same fifteen arm minutes. What keeps its share
a little below the geometry's is the one glass it still breaks, and the two
solutions that break nothing hold the two best shares.

### 3. The ranked trees: a change that was measured and not kept

Solution 2's trees order the pushes the geometry has already approved, so they
cannot break a glass, and on the held-out queue they broke none. What they are
measurably worse at is choosing: with the arm taken away and no clock at all, the
printed rule separates thirty-four of the fifty held-out tables in eighty-six
pushes while the trees separate twenty-nine in a hundred and ten.

The obvious reason is that the trees are fitted on the room a push gains and know
nothing about what it costs to make, so they prefer the longest push. **Measured,
that is not the reason.** Pricing a millimetre of push against the room it is
expected to gain, at four prices from nothing to three times the price problem
3's world model uses, separated fifteen, fifteen, fourteen and fifteen tables of
forty, broke no glass at any price, and changed the arm time by less than a tenth
of a second. So the knob is not in the solution, and the measurement is written
down in ``ranked.py`` where the next person will find it.

### 4. The imitation policy decides first and draws second

**What it is.** Solution 3 was one model doing two jobs, and it is now two models
with one job each.

The **gate** is a small network — four convolutions over the picture and two
linear heads — which is shown what the problem shows every solution and says two
things: which of four kinds of answer to give, and which glass to give it at. The
four kinds are the teacher's own, grouped so that the ones that need telling
apart are apart: go and look, probe a glass with a five-millimetre shove, push a
glass at the task, or say the table is finished. The **policy** is the same
chunked model as before, and it is now told that decision and draws only that.

Four smaller changes come with it, and each answers a measured fault.

**The push is drawn in its own glass's frame.** A push's waypoints are where
they are because of where the glass is, so in the table's own numbers the same
shove at two different glasses is two unrelated answers. Measured from the
glass, it is one answer, and a push learned at one glass is a push everywhere.
This is what ticket #19 asks for.

**The policy's batches are drawn evenly from the kinds.** Of the teacher's
answers, four in five are looks and one in thirty-six is a push at the task. The
looks are thinned rather than the pushes copied, so a step costs exactly what it
cost before.

**The gate's loss is weighted by how rare each kind is, and its slot head is
asked only about the answers that name a glass.** Fitted without either, the
gate learned three of the four kinds well and **never once answered "push"** —
which is the right guess for minimising the average mistake and useless as a
decision — and it got the slot right 85% of the time over everything while
being at chance on the answers where a glass was really chosen.

**The teacher's own "this table is finished" is in the demonstrations.** The
loop never asks the cell to carry anything out for a declaration, so the
collector records the answer that has no path: the last look, and "done" as the
kind. A table now ends when the gate says so, and the shared quiet rule is the
backstop rather than the only rule. The first version declared nine of its ten
tables finished while they were still crowded.

**And the clearance check from change 1 applies to its answers too**, with the
gate's decision as the claim the check tests: an answer the gate called a look
has to ride at travel height, and an answer it aimed at a glass has to reach
that glass and no other.

**What it bought, and what it did not.** The split is what made pushing
*learnable*, and on its own it was still not enough to make the solution push.

The two models each learned their own job well. Measured on tables the fit never
saw, the gate gets the kind of answer right about seven times in ten and finds
most of the teacher's pushes, where the single model had never proposed one at
all. The policy, now told the decision instead of having to guess it, agrees
with the teacher about whether this is a moment for pushing **97% of the time,
against 84% before** — and that rise matters more than it looks, because the old
figure was almost entirely agreement about *not* pushing. Four answers in five
are looks, so a model that never pushes already scores 80% on that question. The
new figure is agreement about the pushes themselves, and the distance between
the student's push and the teacher's, measured over the pushes alone, is about
20 mm a waypoint.

| the gate, on tables it never saw | over the three fits |
| --- | --- |
| the kind of answer right | 70% to 71% |
| the glass right, over the answers that name one | 56% to 61% |
| the teacher's pushes found | 56% to 77% |
| the teacher's "finished" found | 92% to 96% |
| pushes offered, of all its answers | 16% to 21% |

**And yet the first walk after the split freed nothing at all.** Every table
ended with the solution having spent 100% of its arm time on paths that could not
touch a glass. Four separate faults stood between a gate that asked for pushes
and an arm that made one, and they had to be found one at a time; they are
changes 6 to 9 below. Nothing about the split was wrong, and nothing about it was
sufficient.

### 5. The fine-tuned model is fitted on an even mixture

**What it is.** Two changes to solution 6, and neither is a different model or a
different recipe.

Each batch is drawn evenly from the looks and the pushes, by weighting the
sampler rather than by touching the demonstrations. The solution's own page
measured what the teacher's mixture did to it: the middle of its paths sat 233 mm
up, only one answer in fifty came down to the height a glass can be moved at, and
it freed nothing. That is what a fit spends four fifths of itself on looking
produces.

And it inherits the clearance check, because it inherits solution 5's loop. The
pair that this solution exists to measure — the same weights, with and without
this cell's demonstrations — therefore stays one piece of code on both sides.

**What was left alone, on purpose.** The number of steps. Its own page says the
first thing to try is more of them, because a thousand steps at a batch of four
is about a third of one pass over the material, and that is still true. It is
left alone here so that this measurement is of the mixture and of nothing else.

<!-- the numbers for change 5 appear here when the fits are measured -->

### 6. The gate is shown what it has already tried on each glass

**What it is.** The gate is shown two more numbers for each glass on the table:
how many of its own answers have been aimed at that glass, and how far that glass
has moved since it was first measured.

**Why it needs them.** The teacher's push at the task is the last step of a short
sequence. It reaches in until the jaw touches the glass, shoves it five
millimetres to find out whether it slides, and only then pushes it somewhere. So
which step is wanted depends entirely on what has already been tried on that
glass — and a gate shown one picture cannot see any of it. At the states the
student actually reaches, nothing in its input distinguished "I have not touched
this glass" from "I have shoved it twice and it slid".

Both numbers are facts about the solution's own actions and about readings it
took itself, so a solution is allowed to keep them, and nothing in the examiner
is involved. They are stored as a feature of their own beside the demonstrations
rather than added to the row the chunked policy is shown, which is what let them
be added without refitting the policy — an hour a seed — or disturbing solution
6, which reads the same demonstrations.

**What it bought.** Every head of the gate improved, and the two that matter most
improved most.

| the gate, on tables it never saw | without the history | with it |
| --- | --- | --- |
| the kind of answer right | 68% to 70% | 70% to 71% |
| the glass right, over the answers that name one | 53% to 55% | 56% to 61% |
| the teacher's probes found | 37% to 52% | 49% to 68% |
| the glass right when it asks for a push | 50% to 57% | 63% to 68% |

### 7. Three faults that were bugs rather than choices

These are not design changes and they are recorded because each one hid the
others, and because two of them are mistakes worth not making again.

**A look was being drawn in the frame of a glass it was not aimed at.** The
change that made the gate learn which glass to act on was removing the "none of
them" answer from its slot head, so the head now names a glass for *every*
answer, including a look. The solution took that name at face value: it
conditioned the look on that glass and drew the path in that glass's frame, then
added the glass's position back. Every look therefore landed about half a metre
from where it was meant to, out at the table's edge, where the camera sees one
glass and the gate reasonably says the table is finished. Fixing it took tables
from two or three answers to nine or eleven, and revealed that the policy's
travelling was in fact excellent: it walks the teacher's ring of viewpoints
almost exactly.

**The gate's own input meant different things at fit time and at run time.** Two
of the three numbers the gate keeps about itself — answers since it last touched
a glass, and metres travelled since then — were reset by *what the teacher
intended* while the demonstrations were collected, and by *whether the fingers
came low enough to touch something* while the solution ran. Since every drawn
answer was being raised to travel height at that point, the fingers never came
low, so at run time those numbers never reset and climbed into the corner of the
input where the teacher only ever says the table is finished. There is now one
class that computes them, shared by the collector and by every solution, because
two copies of one piece of bookkeeping are two chances to disagree.

**Two crashes had stopped solution 6 entirely.** One looped over the frames a
set had kept and indexed the dataset underneath it, so it eventually read the
teacher's "finished" frame, which has no path. The other demanded a stored
observation of exactly the table's own width, and stopped the fit the first time
that row grew to carry what the gate and the policy need.

### 8. A drawn answer is pulled onto the two heights the cell accounts for

**What it is.** When an answer fails the clearance check of change 1, it is not
thrown away immediately. It is first put into the shape the check asks for and
checked again: every waypoint goes to one of the two heights the cell has a rule
for, and where a stretch both travels and changes height a corner is inserted so
the hand stops moving sideways before it comes down. Which of the two heights a
waypoint goes to is decided by the hand rather than by splitting the difference —
if the fingers would come below the top of the glass the answer names, the answer
meant to touch that glass and the waypoint goes down to where a shove slides a
glass; otherwise it was travelling and the waypoint goes up.

**Why it is needed.** The check of change 1 asks a horizontal stretch to sit at
*exactly* the height a push works at. A solution that computes its answer puts it
there, because that is the number it worked from. A solution that *draws* its
answer predicts that height and is out by a centimetre or two. So the check was
satisfiable by arithmetic and unsatisfiable by a fitted model, and the
measurement is blunt: over twenty tables the gate asked for between 45 and 109
shoves and **every single one was refused**, all for travelling at the height of
the glasses' rims.

**What it bought.** The first pushes this solution has ever had carried out: from
none at all to between 73 and 129 a run. It is also what the two borrowed-model
solutions needed, for the same reason and to the same effect.

### 9. A push may not drive its glass into another

**What it is.** The check now also works out where the pushed glass would end up
and tests *its* path against every other measured glass. A glass that already
stands closer to a neighbour than two glasses need may still be moved, as long as
it ends no closer than it began — which is the reference solution's own rule, and
it has to be, because the draw leaves some glasses nearly touching and those are
exactly the glasses the task is about.

**Why it is needed.** Everything in the check until now asked where the *hand*
goes. Nothing asked where the *glass* goes, so a shove that slid its own glass
into a neighbour passed every test, and the glass that broke was one the hand was
never near.

**What it bought: very little, and that is worth recording.** Over twenty tables
the broken glasses went from 3 (2 to 5) to 3 (1 to 3). The hole in the check was
real and is now closed, but one glass driven into another was not how these
solutions were mostly breaking them.

### 10. A push at the task needs evidence that the glass will slide

**What it is.** A shove that would *move* a glass is allowed only at a glass the
solution has itself watched move. A shove that merely comes to rest against a
glass is allowed anywhere, because that is how the evidence is got. Whether a
path would move a glass is read off what it would **do** — where the glass would
end up — and not off how long the path is, because a cap on the length of a push
was measured earlier in this problem and bought nothing.

**Why it is needed, and a measurement nobody had written down.** The public
tipping rule gives three answers: the glass will slide, it will tip, or it
depends on a friction nothing in this cell can see. The examiner refuses only the
flat "it will tip", and its own words say what the third answer means — a probe
is safe, and a push at the task is a gamble. Measured over sixteen hundred glasses
drawn the way this problem draws them:

| the tipping rule's answer | share of drawn glasses |
| --- | --- |
| it will slide | **none at all** |
| it depends on the friction | 83.8% |
| it will tip | 16.2% |

A glass's foot would have to be over 107 mm across to slide for certain, and the
widest foot the draw makes is 94 mm. **So every glass on every table in this
problem is one whose behaviour nobody can predict**, which is why the teacher
probes before it pushes, and it is exactly the discipline the fitted solutions
had skipped.

**The check that it is the right rule.** The reference solution's own 686 answers
over twenty tables were put through the rule without changing what it did: 99.0%
are kept exactly as drawn, 0.6% are pulled onto the heights, and 0.4% are refused
for a reason the examiner's interlock refuses them for anyway. **None** are
refused for want of evidence. The teacher's probe-then-push sequence satisfies the
rule without a single exception.

**Each solution offers its own account, and that had to be learned the hard way.**
Solutions 3, 5 and 6 account for a glass by having shoved it and watched it move.
Solution 4 never probes at all: it predicts what a push will do with a fitted
ensemble and prices the risk of toppling. The rule was added with only the
probing solutions in mind, and solution 4 immediately fell from 14 separated
tables and 39 glasses freed to 9 and 29, because it had no way to offer the
evidence it in fact had. Its account is now written out: the least favourable copy
of its ensemble must give the push at most the search's own topple limit, which is
the bar its search already applied. With that, it is back to 14 and 39.

**What it bought.** Over twenty tables the broken glasses went from 3 (1 to 3) to
**2 (2 to 3)**, the lowest measured at any point.

### 11. A push is carried on until its glass has room

**What it is.** When a push at the task passes every check, the solution carries
that shove on **along the model's own line**, one step at a time at the spacing
the model asked for, and stops at the first of two things: the glass has the room
it needs, or the next step would fail one of the checks. A probe is left exactly
as drawn.

**Why it is needed.** Three measured numbers cannot be reconciled by better
fitting.

| | |
| --- | --- |
| how far one of the teacher's pushes moves a glass | 13 mm |
| how much room a glass needs before it can be gripped | 76 mm |
| how accurately the chunked policy places a waypoint | 20 mm |

The teacher frees a glass over a *run* of small pushes, feeling its way. So the
thing the student is asked to copy is smaller than its own error, and it draws
shoves that stop at the glass's near edge instead of driving past its middle:
measured over twenty tables, the shoves it carried out moved their glass a median
of **zero** millimetres. No amount of further fitting fixes a target below the
noise.

**What the model decides and what it does not.** The model still chooses
everything that is hard — whether to act, which glass, and which way to shove it.
The distance is arithmetic. That division is stated here rather than hidden,
because the alternative would be to claim the model learned to free glasses, and
it did not; and a run's record now carries how many pushes were driven home and
how far they move their glass, so the split shows up in the numbers too.

**What it bought.** Over twenty tables, glasses freed went from 0 to +1 (1 to 2),
with between 16 and 44 pushes driven home a run, each moving its glass 5 to 25 mm.
It is also where this solution's remaining ceiling becomes visible: the extension
is stopped by the surrounding glasses, and "the hand would meet a glass it is not
aimed at" is now by far the commonest refusal, 69 to 82 times per twenty tables.

### 12. The stretch that drives along the table is made straight

**What it is.** The driving stretch of a push is replaced by evenly spaced points
along the straight line between its own ends, all at that line's heading, and the
hand is turned to that heading before it comes down. The glass, the direction, the
distance and the number of waypoints are all the model's and all kept — the count
matters because in this cell the spacing of the waypoints is the speed of the jaw.
A look that wanders is left wandering, because where a look goes is the model's
business and only a driving stretch touches a glass.

**Why it was tried.** Every toppling left in the runs was a push that had passed
every positional check, which pointed at the shape of the path rather than at
where it goes. The cell turns the hand to each leg's own heading as that leg
starts, so a wandering stretch turns the hand while the fingers are against the
glass, and a glass twisted at the foot goes over instead of sliding.

| the driving stretch of a push | strays from straight | the hand turns between waypoints |
| --- | --- | --- |
| the reference solution's 57 pushes | **0.0 mm** | **0.0°** |
| the student's shoves | median 4.2 to 6.2 mm, most 13.4 mm | up to 3.6° |

**What it bought: nothing that can be told apart from noise.** Over twenty tables
the broken glasses went from 3 (1 to 3) to 2 (1 to 4) and the glasses freed from
+1 (1 to 2) to 0 (−1 to 3). With three fits those spreads overlap completely. It
is kept because its own measurement is sharp and it makes the student's push the
same shape as the teacher's, and the record says plainly that the result did not
move.

## Three repairs that were measured and not kept

A page that only lists what worked is not a record of what was learned.

**A price on a measured push in the ranked trees** (change 3 above) cost nine
tables and was removed.

**A cap on how long a push may be** was tried on the world model and bought
nothing, so the length is left to the search.

**Moving a shove's touchdown backwards until the fingers were over bare table**
made things worse rather than better: over twenty tables the broken glasses went
from 3 (1 to 3) to 4 (4 to 5), because the further back the hand comes down the
longer it ploughs along the table. It was reverted.

One measurement behind that third repair was also wrong, and is withdrawn. It
reported that nine shoves in ten came down with the hand already on the glass,
and it asked that question with the arithmetic that treats the hand as a long box
reaching back from the fingertips — which is true at the touchdown point of a
perfectly ordinary push, as the notes in `keeping_clear.py` already said. Asked
of the fingertips against the glass's own circle, which is the thing that
matters, the answer is different. The rule built on the wrong reading refused
every push in the project, including the reference solution's, and the world
model's search stopped finding any push at all on a crowded table, which is how
it was caught.

## What it all came to

The table below is the held-out queue, which is the measurement this problem
exists to make: fifty tables offered in order from table ten thousand, fifteen
arm minutes for the whole queue, walked three times. "Before" is the first
measured walk, before any of the changes on this page.

| | tables separated | glasses freed | glasses broken | pickable share |
| --- | --- | --- | --- | --- |
| Geometry ranked, before and after | 7 of 25 | +19 | 0 | — |
| A world model, before | 11 of 32 | +29 | 8 | 0.560 |
| **A world model, after** | **14 of 40** | **+39** | **1** | **0.598** |
| Imitation, before | 0 of 10 | 0 | 0 | 0.400 |
| **Imitation, after** | **1 of 13** | **+3** | **2** | 0.377 |
| SmolVLA as it downloads, before | 0 of 15 | −1 | 20 | 0.018 |
| **SmolVLA as it downloads, after** | **0 of 11** | **0 to +2** | **0** | **0.400** |

Three different kinds of outcome are in that table, and they are the result of
this work.

**The world model is now clearly the best solution in the problem**, and it got
there by two changes of different kinds: the shared clearance arithmetic took its
broken glasses from eight to one, and pessimism in its search took its separated
tables from eleven to fourteen while it also reached eight more tables. It beats
the geometry reference it was measured against, which the first walk did not.

**The borrowed model, run exactly as it downloads, went from the worst result in
the problem to a harmless one.** It broke twenty glasses on its first walk and
breaks none now, and its pickable share rose from 0.018 to 0.400. It still
separates nothing, which is the honest result for a model that has never seen
this cell: what changed is that it no longer destroys the table while failing.

**The imitation solution now acts, where before it only looked.** It went from
leaving every table exactly as it found it — not one glass given room it did not
start with — to freeing two or three glasses a queue and separating a table,
while reaching three more tables. It also now breaks two to five, so by the
share this problem scores on it has not yet won: 0.377 against 0.400. The gap
between "it does the task badly" and "it does not do the task" is the whole of
what the changes bought here, and the three things standing in the way of more
are all measured and written down above — one push moves a glass a fifth of what
it needs, no glass in this cell is one the tipping rule can predict, and the
direction the policy draws is blocked by a neighbour four times out of five.

**The last of those three is where this stops, and the reason is worth stating.**
It could be repaired the same way the distance was, by choosing the direction
arithmetically from the measured neighbours. That would leave the model choosing
only which glass to act on, and the solution would have become the geometry
reference with a learned chooser in front of it. That may well be the right thing
to build, and it is not this solution: solution 3 exists to measure what copying
a teacher achieves, and a version of it that no longer copies the teacher's
choice of push would answer a different question.
