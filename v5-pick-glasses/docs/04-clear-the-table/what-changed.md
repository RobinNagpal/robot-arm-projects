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
| Glasses it gave room to | −1 | 0 (0 to +2) |
| Tables attempted | 15 | 11 |

The share rises from almost nothing to 0.400 because a table that loses a glass
counts for nothing at either end, and no table loses one any more. It frees
nothing in two walks of three and two glasses in the third, which is the honest
result for a model that has never seen this cell: 622 of the 624 answers it gave
over the three walks could not account for themselves and were raised, most of
them because the path comes down beside no glass in particular.

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
| Tables attempted | 32 | **40** | 26 |
| Tables separated | 11 | **14** | 10 |
| Tables failed by a topple | 7 | **1** | 0 |
| Glasses broken | 8 | **1** | 0 |
| Glasses it gave room to | +29 | **+39** | +25 |
| Pickable share | 0.560 | **0.598** | 0.627 |
| Thinking an answer | 6 ms | 10 ms | 15 ms |

So the world model now separates more tables than any other solution to this
problem, frees half again as many glasses as the geometry reference, and reaches
half again as many tables in the same fifteen arm minutes. Cut to the twenty-six
tables the reference also reached, it separates eleven against ten and breaks
nothing, so on the same tables it is level or a little ahead. What keeps its
share below the geometry's is no longer the breakages — doing nothing at all on
the tables it broke a glass on would be worth about two points of share — but
the tables it reaches and leaves crowded, which the geometry never reaches at
all.

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

**What it bought.** The fits ran for the first time here, because the two
crashes in change 7 had been stopping them before they reached a single step.
Each seed moves 3.81 million numbers of the model's 454 million, takes about
twenty-six minutes and holds a little over one gigabyte, so the three seeds fit
inside an hour and a half on this laptop.

On the held-out queue the change is the same kind of change the borrowed model
got, and it is just as large.

| solution 6 on the held-out queue | before | after |
| --- | --- | --- |
| tables separated | 0 of 8 | 0 of 10 |
| glasses freed | 0 | 0 |
| glasses broken | 8 (1 to 10) | 1 (0 to 2) |
| pickable share | 0.103 | 0.378 |
| tables it ended by knocking a glass over | 6 of 8 | 1 of 10 |
| tables it ended by saying the table was done | 0 | 9 of 10 |

So the even mixture bought safety and reach, and it bought no competence at all.
Before, the solution drew paths whose middle sat 233 mm above the table and then
destroyed six tables out of eight on the way down, which is why it only reached
eight. Now it comes down at the heights the cell accounts for, survives the
table, and says the table is finished — while freeing nothing. Its distance to
the teacher says the same thing twice: on the pushes it closed from about 90 mm
to about 82 mm, and on the looks it did not close at all, staying near 200 mm
through all three seeds.

**The pair this solution exists for.** Twenty tables from below the held-out
line, the same loop and the same clearance arithmetic on both sides, three walks
each: the only difference is whether this cell's demonstrations were used.

| twenty building tables | the same weights, untrained | fitted here |
| --- | --- | --- |
| tables separated | 0 | 0 |
| glasses freed | 0 (−1 to 0) | 0 (0 to +1) |
| glasses broken | 1 (0 to 3) | 2 (1 to 5) |
| pickable share | 0.369 | 0.369 |
| answers it gave | 335 | 438 |

Read honestly, that is a null result, and it is the useful part of this
solution's measurement. A thousand steps of this cell's demonstrations make the
model act more — a third again as many answers, because it stops declaring the
table finished so early — without making it act better. The single change most
likely to move this is the one deliberately left alone above, which is the
number of steps.

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

### 13. A solution checks its answer against every glass it has measured

**What it is.** A solution now keeps the newest reading of every glass this table
has shown it, and hands all of them to the clearance check. Before this it handed
over the glasses inside the current picture. `Measured` in
`bench/keeping_clear.py` is the bookkeeping, and it lives there for the same
reason `Shoves` does: three solutions need it and the check has to agree with it.

**Why it is needed.** The camera rides on the arm, so a `Look` holds the glasses
in one picture rather than the glasses on the table. A check given that picture
is being asked about part of the table, and the part left out is exactly where a
shove can do its damage: a push that drives its own glass into a neighbour breaks
a glass the hand is never near, so nothing about the hand can catch it, and a
neighbour that is out of frame is in no list to be checked against.

**The geometry solutions never had this hole, and that is where the idea came
from.** `01-one-fixed-nudge/remembered.py` builds a belief about the whole table
out of several looks, averages repeated readings of the same glass, and starts a
glass's average again once it has been pushed. Solutions 1, 2 and 4 all use it.
The fitted solutions were built around answering from one look, so they held one
look — and they are the solutions that broke glasses with pushes. The new class
is the same idea in its simplest form.

**What it bought**, on the twenty tables below the held-out line, three runs
each:

| twenty tables, three runs | glasses broken, before | after | pickable share |
| --- | --- | --- | --- |
| the borrowed model as it downloads | 2 (0 to 4) | **0 (0 to 0)** | 0.369 → **0.393** |
| the same weights through solution 6's loop | 1 (0 to 3) | **0 (0 to 0)** | 0.369 → **0.393** |
| the borrowed model fitted here | 2 (1 to 5) | 2 (1 to **2**) | 0.369 |
| the imitation policy | 2 (1 to 4) | 2 (1 to **3**) | 0.357 → **0.381** |

Those first two rows are the same weights run through two different folders'
loops, so they are two independent measurements of one thing, and they agree
exactly. **The change does most for the solution that aims worst**, which is
what the cause predicts: a model that is not aiming at a particular glass shoves
blindly, and a blind shove is the one most likely to drive its glass into
something nobody is looking at.

**Why it does least for the imitation policy.** Its own record says so: over
twenty tables the memory held only 3 to 25 glasses that the current picture did
not, because the wrist camera usually does see the whole of a four-glass table.
A repair can only be worth the size of the hole it closes.

**And on the held-out queue, which is the score:**

| fifty tables offered from 10,000 | before | with the memory |
| --- | --- | --- |
| the imitation policy's glasses broken | 2 (2 to 5) | **1 (1 to 2)** |
| its tables lost to a topple | 2 (2 to 5) | **1 (1 to 2)** |
| its glasses freed | +3 (+2 to +3) | +1 (+1 to +2) |
| its pickable share | 0.377 | **0.400** |
| the borrowed model's glasses freed | 0 (0 to +2) | **+2 (0 to +2)** |
| its tables separated | 0 (0 to 1) | **1 (0 to 1)** |
| its pickable share | 0.400 | **0.439** |

**The imitation policy's row is a trade and has to be read as one.** Half the
breakage, a higher share, every spread tighter — and two of the three glasses it
used to free are gone, because the arithmetic now refuses more of its pushes. The
trade was taken because this problem treats a toppled glass as unrecoverable: a
table that loses one pays nothing at either end, so one glass saved keeps a whole
table's glasses in the count while one glass freed adds a single glass.

**What was left undone, and the reason.** `Measured` keeps the newest reading
of a glass where the geometry solutions average repeated readings and halve the
camera's error. Averaging would be better, and it needs the caller to say when a
glass has been pushed so that the average can start again — which `Shoves`
already knows. It is not done because the check's whole job is to refuse, it
already grows every glass by four millimetres before it measures, and a
measurement that cannot be told from noise is not worth a change.

### 14. A push is carried on no further than the glass has been watched sliding

**What it is.** Change 11 carries a shove on along its own line until the glass
it names has room. It now also stops at a distance the solution supplies: how
far that glass has already moved under this solution's own shoves. A glass that
has been watched sliding five millimetres has earned a five-millimetre drive, and
one that has slid forty has earned forty, so a push grows as its glass earns it.
The number is the solution's own reading, `Shoves.moved`, and `driven_home` only
obeys it.

**Why it was built, and what measured it.** Every glass the imitation solution
lost went over on a push that had passed the whole clearance check and was then
carried on by the arithmetic. That is a sharper statement than it sounds, and
getting it took a small piece of machinery, because **a solution cannot see its
own breakages**: the table ends the moment a glass goes over, so the look that
would show the damage is never taken. The measurement script therefore keeps each
table's last answer beside how that table ended. Of the five glasses lost over
three fits, all five followed a carried-on push, and in all five the picture held
two or three glasses on a table of four or five.

The reasoning from that record to this rule is the one the reference solution
embodies. Evidence that a glass slides comes from a five-millimetre probe, and a
sixty-millimetre drive is a different action from the one the evidence was
gathered about. The reference frees a glass over a run of small pushes, each
judged by a fresh look, and this rule makes the fitted solutions do the same
thing without taking the choice away from their models.

**What it bought**, over twenty tables and three fits:

| | memory only | with the cap |
| --- | --- | --- |
| the imitation policy's glasses broken | 2 (1 to 3) | **1 (0 to 2)** |
| fit by fit | 3, 2, 1 | **1, 2, 0** |
| its glasses freed | 0 (−1 to +5) | 0 (−1 to +4) |
| its pickable share | 0.381 | **0.393** |
| how far a carried-on push moves its glass | 7, 18, 25 mm | 4, 14, 23 mm |
| pushes carried on | 8, 15, 20 | 15, 16, 21 |
| the borrowed model's glasses broken | 0 (0 to 0) | 0 (0 to **1**) |

The middle rows are the mechanism, and they are worth reading together: the same
number of pushes are carried on, each a little less far, and one fit now walks
all twenty tables without losing a glass — which no fit of this solution had done
since it began pushing at all.

**It does nothing for the borrowed model, and the reason is not noise.** The cap
only applies to a push at a glass the solution has watched sliding, and that
model does not aim at glasses: it comes down somewhere and the arithmetic reads
back which glass the path came nearest. So there is almost nothing for the rule
to act on, and the one glass broken in one run of three is the ordinary
difference between runs of a policy that denoises from fresh noise at every ask.

**What is left, and why no further arithmetic will reach it.** Two of the three
glasses the imitation policy still loses went over while the arithmetic expected
the glass to move 2.7 millimetres and 0.0 millimetres — that is, the extension
added nothing and the shove the policy itself drew tipped the glass. Those
glasses had already been watched sliding, and the tipping rule answers "try it
and see" for every glass this cell draws, so nothing the solution can compute
would have refused that push. What is left is the model that draws the shove, and
that is a fitting problem rather than a checking one.

**And then the held-out queue disagreed with the tables the change was chosen
on.** This is the most useful thing in this entry, so it is written out rather
than smoothed over.

| the imitation policy | memory only | with the cap |
| --- | --- | --- |
| glasses broken, twenty building tables | 2 (1 to 3) | **1 (0 to 2)** |
| glasses broken, the held-out queue | **1 (1 to 2)** | 2 (1 to 3) |
| glasses freed, the held-out queue | +1 (+1 to +2) | **+2 (−1 to +2)** |
| pickable share, the held-out queue | 0.400 (0.378 to 0.404) | 0.400 (0.316 to 0.404) |

Walk by walk, one of the three queue walks is identical with and without the cap,
and the other two each lose one more glass. With three samples on each side and
spreads that overlap this far, **the cap's effect cannot be told from the
noise of this solution on either set of tables** — it is two glasses better on
one set and two worse on the other.

**It is kept, and the reason is the measurement rule rather than the number.**
The change was chosen on the tables below ten thousand, which is where every
choice in this problem is made, and on those tables its evidence was the best
available: one fit walked all twenty without losing a glass for the first time.
The held-out queue is then the score, reported as it came. Reverting the change
*because* the queue came out worse would be choosing by the held-out tables,
which is the one thing the band is there to prevent, and it would make every
earlier number on this page mean less. So the rule stays, the queue's verdict
stands beside it, and the honest summary is that this repair closed a cause that
was real and bought nothing that can be proved.

### 15. The world model is fitted on twice the pushes, and made to pay more for a missed topple

**What it is.** Two changes to solution 4 that only work as a pair. Another
1,200 tables of pushes drawn exactly the way its first round was drawn, which
takes five minutes of laptop time and raises its training set from 6,886 pushes
to 12,253; and ten times the cost, inside the fit, for a topple the model fails
to predict.

**Why the pair.** More pushes make the model aim better and refuse worse, and
the second half of that is not obvious. On the 658 validation pushes the doubled
set cuts the error in where the glass lands from 5.7 mm to 4.3 mm at the median
and from 38.3 mm to 31.7 mm at the ninetieth — and it catches 51 topples of 70
where the old fit caught 57, while raising 94 false alarms where the old fit
raised 116. A model fitted on more data is simply less easily alarmed, and the
search's caution is a *fixed* threshold, so a less alarmed model lets more
marginal pushes through. Raising what a missed topple costs puts the alarm back:
at ten times, the doubled fit catches 56 of 70 and raises 109 false alarms,
which is the old fit's refusal with the new fit's aim.

**What each half does alone, measured on nine clocked walks of a hundred and
fifty tables below the held-out line:**

| | tables separated | glasses freed | glasses lost |
| --- | --- | --- | --- |
| as committed | 14.3 | +40.3 | 3.0 |
| twice the pushes, same cost | — | — | nine more a walk on the unclocked band |
| ten times the cost, same pushes | — | — | thirty-four fewer glasses freed |
| **both** | **15.7** | **+42.3** | **1.7** |

The two middle rows are the point: on the unclocked tuning band, doubling the
pushes alone separated three more tables of two hundred and put nine more
glasses over, and raising the cost alone — on the set before it was doubled —
refused so much that it freed thirty-four fewer glasses. Neither is an
improvement by itself.

**The cost was swept rather than guessed**: at one, ten, twenty and thirty times.
Thirty loses the fewest glasses on the unclocked band and ten wins on the clocked
one, which is the instrument the next section is about, so ten is what the
solution carries.

**And on the held-out queue the change comes out worse**, which is written here
rather than smoothed over:

| fifty tables from 10,000 | as committed | with both changes |
| --- | --- | --- |
| tables attempted | 40 to 41 | 39 to 45 |
| tables separated | 14 | 14 |
| glasses freed | +39 | +36 and +33, in two walk-sets |
| glasses broken | 1 (0 to 2), and 1.5 over six fresh walks | **5** in both walk-sets |
| pickable share | 0.598, and 0.601 over six fresh walks | 0.570 and 0.550 |

Three things were checked before accepting that. The committed model's single
broken glass is not luck: walked six more times it breaks one and a half. The new
model's thirteen broken glasses over three walks fall on nine different tables,
so it is not one bad layout. And the queue is one band of about forty tables
where the selection evidence is three bands of fifty. **It is kept, for the
reason change 14 was kept**: the choice was made below ten thousand on the best
evidence available there, and reverting because the held-out tables disagree is
the one thing the band exists to prevent.

### 16. The imitation policy is fitted on three times the demonstrations

**What it is.** The demonstration set grows from 300 tables to 900, which is
33,687 demonstrations instead of 11,313 and 857 pushes at the task instead of
315. Nothing else about the fit changes. It costs twenty-four minutes of
simulator time and a gigabyte of disk.

**Why it was the next thing to try.** The solution's own record asked for it.
Its policy sat about nine millimetres from its teacher on tables it had been
fitted on and about twenty-four on tables it had not, and two distances that far
apart are the signature of memorising rather than of a model that is short of
ideas — for which the cure is more examples, not more steps.

**A fit does not read every look.** Looks are four answers in five, and the
policy's sampler throws most of them away again before a step is taken, so
reading them all would cost a gigabyte of memory and twenty minutes a run for
frames no step would ever see. The loader therefore takes a cap on looking
frames and keeps every answer that touches a glass, which is why a fit on the
larger set reads 14,994 frames and costs the same fifty-seven minutes it always
did. The gate is fitted without the cap, because how often each kind of answer
really happens is part of what it has to learn.

**What it bought: a millimetre, and half the broken glasses.**

| the policy, three fits each side | 300 tables | 900 tables |
| --- | --- | --- |
| mm a waypoint on tables it was fitted on | 8.7 to 9.8 | 11.5 to 12.2 |
| mm a waypoint on tables it never saw | 23.7 to 23.8 | **22.6 to 23.2** |
| mm a waypoint over the pushes it never saw | 19.8 to 20.5 | **17.7 to 20.4** |

The memorising did stop — the error on fitted tables rose by three millimetres
while the error on unseen tables fell by one — and the error that matters barely
moved. **So the diagnosis was a third right.** The policy was memorising, and
stopping it from memorising did not make it much better, which means what limits
it is the model and the task rather than the number of examples.

The gate says the same thing more bluntly. Fitted on three times the material,
every one of its readings got *wider* rather than better: the kind of answer
right 69 to 74 per cent against 70 to 71, the glass right 56 to 61 against 56 to
61, the teacher's pushes found 56 to 86 per cent against 56 to 77. It was not
short of data either.

**On the tables, the one thing that moved is the breakages.** Over six walks of
the held-out queue a side — six rather than three, because this solution attempts
between nine and thirty-six tables a walk and three walks cannot separate
anything:

| fifty tables from 10,000, six walks | 300 tables | 900 tables |
| --- | --- | --- |
| tables separated | 0 (0 to 1) | 0 (0 to 2) |
| glasses broken | 2 (1 to 2) | **1 (0 to 1)** |
| glasses freed | +2 (−1 to 2) | −1 (−2 to 3) |
| pickable share | 0.400 (0.316 to 0.404) | 0.361 (0.303 to 0.423) |

With a spread of about half a glass on each side, halving the broken glasses is
a real difference; the share differs by about one and a half standard errors of
the difference and the freed glasses overlap completely. **It is kept for the
breakages**, and the record says plainly that it bought nothing else.

### A choice made on the wrong instrument, and the instrument that replaced it

This belongs with the two changes above because it cost two wrong turns, and
because every number on this page from here on is measured differently.

**The tuning band and the score ask different questions.** A measurement run
over two hundred tables gives every table as much arm time as it wants, so it
says whether a table *can* be separated. The score gives fifteen arm minutes for
fifty tables, so it says how much gets done before the clock stops. A change
that trades time for thoroughness wins the first and loses the second, and that
is exactly what happened: two configurations of the world model were chosen on
the unclocked band, and both came back from the held-out queue with a lower
share than the model they replaced.

**The examiner already had what was needed.** Its judging takes the band of
tables as an argument, so a clocked queue of fifty tables below the held-out
line, walked three times, is the score's own shape on tables that may be chosen
on. Solution 4 now has a ``select`` command for it, and the choices above were
made on three such bands — nine walks over a hundred and fifty tables — rather
than on the unclocked two hundred.

**One fifty-table queue is still not enough.** The same model scored 0.647 on
the band from 500 and 0.570 on the held-out band, which is why three bands are
walked and pooled rather than one.

## Nine repairs that were measured and not kept

A page that only lists what worked is not a record of what was learned.

**A price on a measured push in the ranked trees** (change 3 above) cost nine
tables and was removed.

**A cap on how long a push may be** was tried on the world model and bought
nothing, so the length is left to the search.

**Moving a shove's touchdown backwards until the fingers were over bare table**
made things worse rather than better: over twenty tables the broken glasses went
from 3 (1 to 3) to 4 (4 to 5), because the further back the hand comes down the
longer it ploughs along the table. It was reverted.

**Trying the gate's next choice of glass when the arithmetic refuses the first**
was built, measured and taken out again. The gate scores every slot, so it has an
order over the glasses and not only a favourite, and the idea was to walk that
order and answer at the first glass the clearance check would allow — the model
still choosing, the arithmetic keeping only the power to refuse. Over twenty
tables the three fits broke 2, 4 and 5 glasses against 3, 2 and 1 with the
memory alone, and the one separated table was lost.

The run's own record says why it was never likely to help. The gate's first
choice was accepted 401 to 751 times in a walk and its later choices only 23 to
39 times, so the change touched about one answer in twenty — and those were
answers at glasses the gate itself had ranked low, where its slot accuracy of 56
to 61 per cent makes a lower choice more often wrong than right. **An answer the
arithmetic refuses is sometimes the better outcome**, and a solution that keeps
asking until something is allowed is choosing by what is allowed rather than by
what it believes.

**A solution cannot diagnose its own broken glasses, and finding that out cost a
measurement.** Every reading carries whether the glass is standing, so a
solution ought to be able to notice a glass on its side and record the answer it
gave just before. That was built, and it recorded nothing at all on runs that
broke eleven glasses between them. The reason is the examiner: a table ends the
moment a glass goes over, so the look that would show the damage is never taken.
The diagnosis now lives in the measurement script, which pairs each table's last
answer with how that table ended, and that is the only place it can live.

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

**Collecting the pushes the copies disagree about** was built, measured and left
out of the fit, and it is the most interesting of these because the idea is
sound and the consequence is not. A third collecting round draws forty candidate
pushes a time and makes the one the three copies disagree about most, where
disagreement is the spread of their predicted landings divided by the room a
glass needs, plus the spread of their chances of a topple. Those pushes are
genuinely the dangerous ones: **17.3% of them put a glass over, against 10.4%
for pushes drawn at random and 6.3% for the pushes the search itself chooses.**
Fitted on them, the model separated the same number of tables and lost two and a
half more glasses a seed on the tuning band. The round stays in the collector
behind its own flag, with the file named so that the fit cannot read it by
accident, because the measurement is worth repeating and the data is not worth
fitting on.

**Tightening the search's caution** was measured on four settings and two
models, and it never bought anything. Against the standard one chance in a
hundred, the three-round model at three in a thousand lost four fewer glasses
and a table, and at one in a thousand it lost five more; the doubled-pushes model
lost 19, 24, 26 and 27 glasses at one in a hundred, three in a thousand, one in
a thousand and three in ten thousand. **A threshold cannot refuse what the model
gives no chance at all**, and the pushes that topple glasses are exactly those.

**Testing a glass the copies disagree about, before pushing it**, is the
synthesis of all of the above and it does not work. The world model never probes;
the reference does, and the disagreement number says which pushes are worth
probing, so a doubted push was answered with the reference's own five-millimetre
shove first. Measured on nine clocked walks at three thresholds:

| | tables separated | glasses freed | glasses lost | share |
| --- | --- | --- | --- | --- |
| no testing | **15.7** | **+42.3** | 1.7 | **0.632** |
| test when the doubt is 0.10 or more | 14.7 | +41.0 | 1.7 | 0.621 |
| test when the doubt is 0.05 or more | 13.7 | +37.7 | 1.7 | 0.604 |
| test when the doubt is 0.03 or more | 11.3 | +34.7 | 2.3 | 0.591 |

Every threshold costs tables and saves no glasses at all. The reason is the
measurement in change 10: a five-millimetre test says whether a glass slides a
little, and a glass goes over under a long push that the tipping rule cannot
predict for any glass in this cell. The reference survives that by freeing a
glass over a run of small pushes judged one at a time; this solution makes one
long push, so the test tells it nothing it can use. The branch was taken out
again and the arithmetic it needed stayed, because the collector uses it.

**Fitting the borrowed model for three times as many steps, on three times the
demonstrations**, was the last thing tried and it bought nothing on the tables.
The distance from its teacher was the one number in that solution's record still
falling when the fit stopped, and solution 3's larger demonstration set was
already collected, so the two were raised together: three thousand steps instead
of a thousand, over the twelve thousand frames collected from nine hundred
tables. It costs eighty minutes a seed instead of twenty-seven.

**The fit's own record separates the steps from the data**, because it measures
the distance to the teacher every five hundred steps. At the same thousand steps,
three times the demonstrations moved the median distance over all kinds from
134 mm to 136 mm, which is nothing beside a spread thirty millimetres wide, and
it moved the distance over the pushes the wrong way. The extra two thousand steps
then took the distance over all kinds to 85 mm and over the pushes to 74 mm. **So
the steps did the work and the larger set never showed**, which is the opposite
of change 16, where the data was what moved and the step count was already
enough.

On the tables, measured on the same twenty below the held-out line that this
solution's pair measurement uses, three walks a side:

| twenty tables, three walks | 1,000 steps on 4,000 frames | 3,000 steps on 12,000 frames |
| --- | --- | --- |
| tables separated | 0 (0 to 0) | 0 (0 to 1) |
| glasses broken | 2 (1 to 3) | 2 (1 to 2) |
| glasses freed | +2 (0 to +3) | 0 (0 to +2) |
| pickable share | 0.369 | 0.369 |
| lowest point of a chunk | 112 mm | 91 mm |
| travel across the table | 351 mm | 330 mm |

Everything about the *form* of the answers moved further towards the teacher and
nothing about the outcome moved with it, which is change 5's finding in a
sharper form: what limits this solution is not how well it copies its teacher's
motion. One of the three walks separated a table, which no fit of this solution
had managed before, and one table in sixty is not yet a result. The longer fit
was not kept, because below the line the two fits tie on every scored count and
the longer one costs three times the machine time. The held-out queue agrees
without being asked: it scored 0.345 there against 0.405, and one of its three
walks broke three glasses.

## What it all came to

The table below is the held-out queue, which is the measurement this problem
exists to make: fifty tables offered in order from table ten thousand, fifteen
arm minutes for the whole queue, walked three times. "Before" is the first
measured walk, before any of the changes on this page.

| | tables separated | glasses freed | glasses broken | pickable share |
| --- | --- | --- | --- | --- |
| Geometry ranked, before and after | 7 of 25 | +19 | 0 | — |
| A world model, before | 11 of 32 | +29 | 8 | 0.560 |
| **A world model, after** | **14 of 39** | **+33** | 5 | 0.550 |
| Imitation, before | 0 of 10 | 0 | 0 | 0.400 |
| **Imitation, after** | 0 of 14, 2 in one walk | −1 | 1 | 0.359 |
| SmolVLA as it downloads, before | 0 of 15 | −1 | 20 | 0.018 |
| **SmolVLA as it downloads, after** | **1 of 11** | **+2** | **0** | **0.439** |
| SmolVLA fine-tuned, before | 0 of 8 | 0 | 8 | 0.103 |
| **SmolVLA fine-tuned, after** | **0 of 11** | 0 | **0** | **0.405** |

Three different kinds of outcome are in that table, and they are the result of
this work.

**The world model is now the best solution in the problem**, and it got there by
changes of three different kinds. The shared clearance arithmetic took its broken
glasses from eight to one. Pessimism in its search took its separated tables from
eleven to fourteen while it also reached seven more tables. Then change 15 traded
some of the first gain back for the second: fitted on twice the pushes and
charged more for a missed topple, it breaks five glasses a queue instead of one.
On the twenty-six tables the geometry reference also reaches it is level with it,
ten tables and twenty-four glasses against ten tables and twenty-five, and what
it wins on is the clock, because a separated table costs it twenty-five arm
seconds against the reference's forty-four.

**The two borrowed models went from the worst results in the problem to
harmless ones.** Run exactly as it downloads, the model broke twenty glasses on
its first walk and breaks none now, and its pickable share rose from 0.018 to
0.439. Fitted on this cell's demonstrations, it broke eight and now breaks none,
and its share rose from 0.103 to 0.405. Neither separates a table on purpose,
which is the honest result for a half-billion-number model given three hundred
tables and a thousand steps: what changed is that they no longer destroy the
table while failing.

**The pair the fine-tuned model exists for says what fine-tuning bought, and it
is not nothing.** On the same twenty tables, through the same loop, with the
same arithmetic on both sides, the fitted model frees two glasses where the
untrained one frees none — and topples two where the untrained one topples none,
so its share comes out slightly lower. It draws its paths at the length and speed
of its teacher's pushes and comes down to pushing height nearly twice as often.
**Fitting bought work and it did not buy care.**

**The imitation solution now acts, where before it only looked.** It went from
leaving every table exactly as it found it — not one glass given room it did not
start with — to pushing glasses about, separating two tables in one walk of
three, and reaching fourteen tables instead of ten. By the share this problem
scores on it has not won anything: 0.359 against the 0.400 it scored while doing
nothing, with a spread from 0.303 to 0.423 that holds both. It ends a queue one
glass down on balance and breaks one. **So what the changes bought here is a
solution that attempts the task and fails at it, in place of one that did not
attempt it**, and the three things standing in the way of more are all measured
and written down above — one push moves a glass a fifth of what it needs, no
glass in this cell is one the tipping rule can predict, and the direction the
policy draws is blocked by a neighbour four times out of five.

**And one honest word about the share.** The imitation policy scored 0.400 when
it moved nothing and scores 0.359 now that it pushes glasses about, which reads
like a solution that got worse when what it really did was start acting: a glass
it topples forfeits its table, and a table it attempts and leaves crowded still
counts every glass on it. A single share cannot tell "moved nothing" from
"tried and failed", which is why every page here reports the glasses freed and
the glasses broken beside it. The card for this problem is three numbers, not
one.

**The last of those three is where this stops, and the reason is worth stating.**
It could be repaired the same way the distance was, by choosing the direction
arithmetically from the measured neighbours. That would leave the model choosing
only which glass to act on, and the solution would have become the geometry
reference with a learned chooser in front of it. That may well be the right thing
to build, and it is not this solution: solution 3 exists to measure what copying
a teacher achieves, and a version of it that no longer copies the teacher's
choice of push would answer a different question.
