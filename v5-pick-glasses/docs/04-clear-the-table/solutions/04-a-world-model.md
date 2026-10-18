# Solution 4 — a world model, in a cell with no camera above the table

> **What it uses** — PyTorch, and the cell through
> [problem 4's examiner](../the-examiner.md). Three copies of one small
> network, written and fitted in this cell. Nothing is downloaded.
> **What it does** — it has learned what a push does to a table. On every turn
> it tries a few thousand candidate pushes against that learned model instead
> of against the table, throws away the ones it believes would put a glass
> over, and makes the best of what is left.
> **How it differs from the others** — it is the only solution here that learns
> *what will happen* rather than *what to do*, and the only learned solution
> whose every number was fitted on this cell.
> **What it costs** — thirteen hours of the arm's own time to collect the
> pushes it learns from, and nine minutes of a laptop to fit them. Answering is
> cheap: six milliseconds a turn, which is the least of any solution in this
> problem.

> **The cell is described once, in [the cell](../../the-cell.md).** The method
> itself — what a forward model is, how a search over sampled candidates works,
> and why three copies of one network measure what the network does not know —
> is described once in
> [problem 3's page for the same method](../../03-push-glasses-apart/solutions/04-a-world-model.md).
> This page covers only what problem 4 changes, and what problem 4 measured.

## Introduction

This page answers [problem 4](../problem.md) with a learned model of what a
push does.

Problem 4 is [problem 3](../../03-push-glasses-apart/README.md) with two helps
taken away. The camera above the table is gone, so the arm carries its own
camera and seeing costs motion and time. The push-by-push hand-over is gone, so
nothing counts the pushes and the solution has to say for itself when a table
is finished. Everything else — the glasses, the physics, the hand and the
measurement error — is the same cell.

This solution was ported to that, and the port raises one question worth
measuring. A learned model of the physics should be worth *more* here than it
was in problem 3, because the thing it replaces is now expensive. In problem 3
the geometry reference found out what a push would do by making a small test
push and looking at the result, and looking was free. Here that test push is
arm seconds, and arm seconds are the budget. So a solution that can predict
what the test push would have shown is buying something real.

The measurement says it does buy that. **It separates more tables than any
other solution to this problem, gives room to half again as many glasses as the
geometry reference, and reaches nearly twice as many tables in the same fifteen
arm minutes.** It got there in two stages, and the second one is the useful
part of this page. The first measurement of it broke eight glasses in a walk and
scored below the geometry because of them; a table that loses a glass is worth
nothing at all, so those tables were removed from its score rather than
discounted. Nothing about the model was then changed. What changed is how the
search treats the model's own estimates, and the breakages fell from eight to
one. By the end of this page you will know:

- how this solution was put to a problem with no view of the whole table;
- why a search that asks a model about thousands of pushes and takes the best
  answer is choosing the model's largest error, and the three changes that stop
  it doing that;
- what the held-out queue measured, before and after those changes;
- which tables it still breaks a glass on, and what the model believed about
  the pushes that broke them.

Read [the examiner](../the-examiner.md) first. It defines what a solution is
shown, what it may answer, why saying "done" is part of the job, and how a walk
of the queue is marked.

## A film of one table

Here is this solution clearing one table, recorded in the simulator and playing
at one and a half times real speed.

[Watch the film (11 s)](../../../videos/04-clear-the-table/04-a-world-model.mp4)

It is table 10001 of the held-out fifty, the one table every solution in
problem 4 is filmed on, so this film and
[the reference's](01-one-fixed-nudge.md#a-film-of-one-table) are of the same
glasses in the same places.
[The comparison page](../../../04-clear-the-table/results/README.md#a-film-of-each-solution)
says how the table was chosen.

**The film shows this solution's one real advantage.** It separates the table
with a **single push**, in twenty answers and twenty-two arm seconds, where the
reference needs three pushes and twenty-eight seconds and the ranked chooser
five and thirty-five. The search is choosing where to put the hand by asking a
fitted model what each candidate push would do, and on this table it finds in
one go a push that the geometry takes three attempts to arrive at. That is the
same thing the row "arm seconds for a table it separated" reports over the
whole queue, where this solution needs 25.4 seconds to the reference's 43.6.

**It is not a lucky run.** This solution separated table 10001 in all three
scored walks of the queue, in twenty answers and about twenty-two arm seconds
each time, so the film is what it reliably does here. The search is seeded as
well, so it runs this way every time it is filmed.

## What the port had to add

The method is problem 3's and is unchanged in its middle. What changed is
everything around the middle, because the shape of the problem changed.

**It has to go and look.** A solution is never handed the table. It is handed
one look at a time, and a look holds only the glasses the camera on the wrist
can see from where the jaw is standing. So this solution borrows the geometry
reference's answer to that: a ring of eight standing places around the table,
each chosen so that the camera frames a different part of it. Walking that ring
once and merging what was seen at each stand gives one belief about the whole
table, and the belief is what the search plans against. Walking the ring costs
about eight arm seconds, and it is paid at the start of every table and again
before the solution says it is finished, because a claim that a table needs
nothing more is a claim about the whole table and not about the part in front
of the hand.

**It has to answer with a path rather than with a push.** Problem 3 accepted a
push — a glass, a direction and a distance — and the cell felt its way in: it
crept the fingers forward until a force sensor found the glass, and pushed from
wherever that turned out to be. Problem 4 accepts a run of waypoints for the
jaw, and a run of waypoints cannot feel. So how far the hand has to reach in
before it touches the glass has to be known *before* the path is written, and
that distance is not small: the hand meets a glass at the hand's own working
height, where a stemmed glass is its stem.

That one number is where the saving in this solution lives. The geometry
reference finds the distance out by poking — drive the fingertips five
millimetres deeper, look, see whether the glass moved, and repeat — and every
round of that is arm seconds. Here it is simply another thing the model has an
opinion about, so the poking is replaced by a prediction. That is the whole of
the trade this solution makes, and the held-out queue is what prices it.

**It has to say when it is done.** It says so when its search can find no push
worth making on a table it has just looked at from every one of the eight
stands.

## How it works, end to end

Each line below is one turn of the loop, and a turn is one look answered by one
path.

1. Walk the ring of eight stands and merge what was seen into one belief about
   the table.
2. For every glass the belief says is still crowded, sample candidate pushes
   and score them against the learned model. Drop a candidate if any copy of
   the model gives it more than one chance in a hundred of putting something
   over, or if the glass it moves would end up outside the zone the glasses
   live in, or if the model predicts a movement longer than the push itself,
   which is the model answering about something it has never seen.
3. Make the best surviving push over all the crowded glasses, unless the cell's
   own safety interlock would refuse it, in which case it is dropped here
   rather than answered — a refused path moves the arm nowhere, so answering it
   would hand the solution the same table back and waste the tries it allows
   itself for that glass.
4. Look again at what the push did. Usually this costs nothing at all, because
   the jaw is already standing behind the glass it pushed and facing it, so
   another frame from a standing arm is free.
5. Go back to step 2. When no push is worth making, walk the ring again, and if
   there is still nothing, say the table is finished.

Only step 2 is this solution's own. The rest is the geometry reference's loop,
which was written to be reused this way.

## What the model is shown, and what it answers

The model is shown twenty-six numbers: the measured height, widest width and
foot of the glass to be pushed; the push itself, which is where across the
glass the hand meets it, how far it pushes, and how far it reaches in before it
expects to touch; and where up to four neighbouring glasses stand with how big
they are. Everything is measured along the push and across it, so a push
towards the north and the same push towards the east are one example rather
than two.

It answers eleven numbers: where the pushed glass ends up, where each
neighbour ends up, and the chance that something goes over.

Three copies of the same network are fitted from different starting weights on
the same pushes. Where the copies agree, the model has seen pushes like this
one. Where they disagree, it has not, and the search takes the worst of their
three topple chances rather than the average, so disagreement makes a candidate
less attractive instead of more.

## What it cost the arm to learn

Every figure here is the arm's time, because in problem 4 that is what a push
costs.

| | tables | pushes | arm time |
|---|---|---|---|
| First round, pushes drawn at random | 1,200 | 5,404 | 9.4 hours |
| The same round again, on later tables | 1,200 | 5,367 | 9.5 hours |
| Second round, the search's own pushes | 300 | 1,482 | 2.4 hours |
| Validation, never fitted on | 150 | 658 | 1.2 hours |

**Twenty-three hours of the arm, where problem 3 collected two and a half times
as many pushes for nothing at all.** That is the clearest single consequence of taking the
overhead camera away. A push in problem 3 cost one call to a camera that saw
the whole table. Here the arm has to walk the ring before it knows where
anything is, and walk to a stand again whenever the glass it pushed is hidden
from where it is standing, so a collecting table gives back four or five
pushes for about twenty-eight arm seconds.

On the 658 validation pushes, made on tables nothing was fitted on, 254 really
moved a glass. The model puts those 13.3 mm from where they land at the median
and 47 mm out at the tenth-worst in a hundred. Problem 3's model, fitted on two
and a half times the data, manages 6.5 mm and 39 mm. The topple filter the
search works at catches 56 of the 70 pushes that really put a glass over, and
flags 109 of the 588 that did not. **Those two sentences are the whole character
of this solution, and the rest of this page is what they cost on a real queue.**

**The second batch of random pushes is what moved those numbers, and it had to
be paired with a change to the fit.** More pushes make the model aim better and
refuse worse: on its own the doubled set lands a glass 12.8 mm out instead of
14.0, and catches 51 topples of 70 instead of 57 while raising 94 false alarms
instead of 116. A model fitted on more data is simply less easily alarmed, and
the search's caution is a *fixed* threshold, so a less alarmed model lets more
marginal pushes through and breaks more glasses. The fit therefore now charges
ten times as much for a topple it fails to predict, which restores the refusal
without giving back the aim. Neither change is an improvement on its own, and
[what changed](../what-changed.md) has all four corners of that square.

## How a walk of the queue is marked

Two things about the marking have to be clear before any number below can be
read, and both are the examiner's rather than this solution's.

**One budget for the whole queue.** A solution is handed fifty tables in order,
starting at table ten thousand, and fifteen minutes of arm time for all of them
together. Each table may spend as much of what is left as it needs. So speed is
part of the score rather than a column beside it: a solution that clears a
table beautifully in forty seconds reaches fewer tables than one that clears it
roughly in twenty, and the card shows both halves of that.

**A table the arm never worked on is not counted.** Near the end of the budget
the clock holds only a few seconds, so a table can be handed over, asked for a
path, and have the path turned down for not fitting in the time left. The arm
never moves and the table comes straight back. Such a table is left out of
every count, because counting it would claim the solution reached further down
the list than it did, and would also drop every glass on it into the share of
glasses made pickable as a glass left crowded. A table where the arm did move
and then ran out of time is a real attempt and is counted.

The queue was walked three times, because the search draws its candidates at
random and the same table asked twice is not answered the same way. Every
figure below is the median of the three walks with the three values beside it.

## What the held-out queue measured

The geometry reference's column is beside it, because it is the thing this
solution is a replacement for. Both spend essentially the whole fifteen
minutes, so how far each got down the list is set by what a table costs it.

| fifty tables offered from 10,000 | the geometry reference | **this, the model** | the same fit before the pushes doubled |
|---|---|---|---|
| Tables attempted | 26 | **39** (45, 38, 39) | 40 |
| Glasses on those tables | 102 | 155 (179, 151, 155) | 160 |
| Tables separated, nothing broken | 10 | **14** (14, 12, 15) | 14 |
| Tables failed by a topple | **0** | 5 (6, 5, 2) | 1 |
| Tables left unfinished | 16 | 22 (25, 21, 22) | 25 |
| Glasses pickable at the end | 64 | 92 (92, 83, 99) | 98 |
| Of those, had room already | 39 | 57 (59, 51, 57) | 59 |
| Glasses it gave room to | +25 | **+33** (+33, +32, +42) | +39 |
| Share of glasses pickable | **0.627** | 0.550 (0.514, 0.550, 0.639) | 0.598 |
| Glasses broken | **0** | 5 (6, 5, 2) | 1 |
| It declared a table finished | 24 of 26 | 36 of 39 (38, 32, 36) | 39 of 40 |
| …while the table was still crowded | 14 | 22 (24, 20, 22) | 25 |
| Arm seconds for a table it separated | 43.6 | **25.3** (23.9, 25.3, 28.3) | 25.4 |
| Thinking an answer | 15 ms | **11 ms** | 10 ms |
| Pushes the cell's interlock refused | 0 | 0 | 0 |

**Three readings come out of that card.**

The first is that **the saving it was ported to make is real.** A table it
separates costs it 25.4 arm seconds against the reference's 43.6. That number
is worth more than it looks, because it is averaged over tables that were
actually finished, so a table cut short by a falling glass cannot flatter it.
The saving is about forty per cent off a win, and it is the whole of the extra
reach: thirty-nine tables attempted against twenty-six.

The second is that **it is still the best separator measured on this problem.**
Fourteen tables against the reference's ten, with the three walks giving 14, 12
and 15 while the reference is deterministic and gives 10 every time. The fit
before the pushes were doubled also separated fourteen, so this round did not
buy tables here; what it bought was measured on a hundred and fifty tables below
the held-out line, where it separates 15.7 a walk against 14.3.

The third is that **its share of pickable glasses fell, from 0.598 to 0.550,
and the broken glasses are why.** Five tables a walk are forfeited where one was
before, and a forfeited table pays nothing for any glass on it. The next two
sections take that apart: the breakages are worth about three points of the
seven-point gap to the reference, and the tables reached and left crowded are
the rest.

**One more comparison is worth making, because the card above compares walks of
different lengths.** A faster solution reaches further down the queue, and the
tables it reaches there are not the tables the reference was scored on. Cut both
walks to the twenty-six tables the reference reached, which the comparison page
does for every row, and this solution separates ten tables against ten, frees
twenty-two to twenty-nine glasses against twenty-five, and breaks one to three.
So on the same tables it is now level on tables separated and behind on glasses,
and its advantage is reaching half again as many tables in the same quarter of
an hour.

**And one caution about all of the above.** This card is forty tables walked
three times, and the choice to double the pushes was made on a hundred and fifty
tables walked nine times, where this fit loses fewer glasses rather than more.
One band disagrees with three, in the opposite direction, over nine different
tables. [What changed](../what-changed.md) says what was checked before that was
accepted and why the change was kept anyway.

## Why breaking glasses costs it the win

A table where a glass went over earns nothing at all. Not a reduced amount:
nothing. Every glass on it leaves the pickable count while all of them stay in
the total, including the glasses that already had room before the arm arrived.
The examiner is explicit about why — if a lost table still paid out for its
other glasses, a hard and risky shove would be close to free, and a method
could gamble its way up the card.

That rule has decided this solution's score at every measurement but one. On
its first walks, 19, 30 and 27 of the 125 glasses it met stood on tables it
broke a glass on; doing nothing at all on those tables would have been worth
about seven points of share, and seven points was the whole of the gap to the
geometry. The round that made the search pessimistic brought that to one table a
walk, and the breakages stopped mattering. **This round's change to the fit has
brought it back**: twenty-five, twenty and seven glasses stood on the tables it
forfeited in the three walks, which is between a twentieth and a seventh of
everything it touched.

The same arithmetic says how much that costs. Take the share as scored, then ask
what it would have been had the forfeited tables merely been left crowded, and
then had they been separated:

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Share of glasses pickable, as scored | 0.514 | 0.550 | 0.639 |
| …had the broken tables merely been left crowded | 0.559 | 0.589 | 0.652 |
| …had they been separated instead | 0.654 | 0.682 | 0.684 |

The middle row is worth four and a half, three and nine tenths, and one and
three tenths points of share, so **the breakages cost about three points of the
seven-point gap to the reference's 0.627, and the tables left crowded cost the
rest.** The third walk is the one to read against the other two: it forfeited
two tables rather than six and scored 0.639, which is above the reference. The
bottom row says where the ceiling is — separating every table it forfeited would
put it at about 0.68, and twenty-two tables reached and left crowded are what
stands between.

## Which tables it breaks, and which it separates

The per-table rows are worth reading, because where the breakages fall says
whether they are a property of this queue or of this fit.

| tables | walks | separated | failed by a topple | glasses given room | glasses broken |
|---|---|---|---|---|---|
| The first eighteen, 10,000 to 10,017 | 54 | 9, 8, 9 of 18 | 1, 2, 0 | +20, +18, +22 | 1, 2, 0 of 204 |
| 10,018 to 10,025 | 24 | 1, 2, 1 of 8 | 1, 1, 1 | +2, +6, +7 | 1, 1, 1 of 102 |
| 10,026 onwards | 44 | 4, 2, 5 | 4, 2, 1 | +11, +8, +13 | 4, 2, 1 of 179 |

**Thirteen glasses went over in three walks, spread over nine different
tables**, and three of those tables lose one in more than one walk: 10,011 and
10,022 twice each and 10,035 in all three. So about half the breakages are a
handful of layouts this fit handles badly and the rest are scattered. The first
eighteen tables, which the fit before this one walked fifty-four times without
breaking anything, now lose one in two walks of three.

The stretch from 10,018 to 10,025 is still the hard part of this queue — the
geometry reference walks it with time to spare, separates **none** of those
eight and gives room to **one** glass in total — and this solution still
separates one or two of them every walk while losing one glass there every walk.
Being willing to act where the geometry declines is what buys both.

Lining the two solutions up over the twenty-six tables the reference reached,
this fit breaks a glass on five or six of them a walk where the fit before it
broke one, and separates ten against the reference's ten. **So the extra wins
and the breakages come out of the same decision as ever, and this round moved
the balance of it the wrong way on this band** — which is the disagreement with
the hundred and fifty selection tables that [what changed](../what-changed.md)
sets out.

## What the model believed about the pushes that broke a glass

This page used to end its argument here with a question it could not answer: is
the model wrong, or does the search trust it too far? Both readings fitted the
rows equally well, and what would have settled it was a record of what the model
believed about every push it made, beside what the table then did. Nothing saved
that. It is saved now.

**The answer is that the model was confident and wrong.** On the twenty tuning
tables, where five glasses went over, the five pushes that put them over were
given a chance of toppling something of **one in a hundred thousand at the
median**, and the worst of them one in three hundred — which is still inside the
limit the search works to. The copies of the model did not disagree about them,
so the pessimism that removed most of the breakages cannot help here: there was
no disagreement to charge for.

**And they were long.** The five pushes that broke a glass travelled 48 mm at
the median; every other push made on those tables travelled 16 mm. A long push
is where this model has the least data and the most to be wrong about, and it is
also where being wrong does the most damage, because the glass has further to go
and more neighbours to meet on the way.

That was a statement about the *data* rather than about the search, and it has
now been acted on. The pushes were doubled, which improved where the model
thinks a glass lands by about a millimetre at the median and three at the
ninetieth — and did not stop the long pushes going wrong. **So the reading was
right and the remedy was not enough**, and the three things tried alongside it
all failed for one reason: a threshold cannot refuse a push the model gives no
chance at all, and a five-millimetre test cannot tell you what a fifty-millimetre
push will do in a cell where the tipping rule can predict no glass whatsoever.

## Why the model is confident and wrong, which is a property of the search

The last section leaves one question open, and it is the important one: the part
of the model that judges toppling was fitted on thousands of pushes and told
what each of them did, so why is it so badly wrong about these few? The answer
is not that it is a poor judge of pushes. It is that nobody had ever asked it
about the pushes it is actually used on.

**The set a model is checked on has to be made the way the model is used.** The
check set this solution has always reported is pushes drawn at random, because
that is how the first collecting round was made. The search does not make random
pushes: it looks at a few thousand candidates and takes the one the model likes
best. So a second check set was collected, on 150 tables nothing was fitted on,
with the search choosing every push exactly as it does in a run. The same model
was then read on both sets.

| at a chance of one in a hundred | toppling pushes caught | safe pushes flagged |
| --- | --- | --- |
| on pushes drawn at random | 56 of 70 | 109 of 588 |
| on pushes the search chose | **13 of 40** | 33 of 725 |

**A model that catches four topples in five becomes a model that catches one in
three, and the only thing that changed is who chose the pushes.** This is the
winner's curse, and it is worth stating plainly because it applies to every
solution that searches over its own predictions. The search is maximising over
estimates that carry error, so it is drawn to the candidates whose estimates are
wrong in its favour. Among the pushes it brings back, the ones the model
mis-judges are over-represented by construction. The head's mistakes are not
scattered through the solution's answers — they *are* the solution's answers
that break glasses.

Two consequences follow. The first is that the three repairs above could not
have worked: a limit, a price and a test all act on the number the head
produces, and on these pushes that number is near zero however it is treated.
The second is the obvious cure, which is to teach the head on the pushes the
search chooses, and that was measured too.

**Fitting on the search's own pushes fixes the head and not the table.** A
second planned round of 300 tables was collected with this model, rather than
the first planned round's model of three weeks earlier, and the fit on it catches
22 of 40 instead of 13, while its aim on those pushes improves from 7.1 mm to
6.3 mm. Over nine clocked walks of fifty tables it separates 16.6 tables against
15.7, frees 45.0 glasses against 42.3, and breaks 3.1 against 1.7. With the
better head the caution limit at last does something — tightened to three in a
thousand it takes breakages from 3.1 to 2.3 — and never below the kept fit's
1.7. Eight configurations of the two fits were walked in all, and the share
ranges from 0.604 to 0.640 with no ordering that survives the spreads.

So the round-two fit was not kept, and the reason is the clearest sentence this
solution's record has produced: **a more capable model here buys more work, and
more work on a crowded table means more glasses on their sides.** What decides
the remaining topples is friction and the exact contact between a finger and a
glass, which no camera in this cell can see, so the next thing worth building is
a different account of toppling rather than another setting in front of this one.

## The knob that trades some of it back, and why it was not turned

The search pays a price for every millimetre it pushes, and that price is the
setting that trades room against arm time and against risk. A longer push makes
more room, takes longer, and is more likely to put something over — and the
record above says the pushes that broke a glass were three times longer than the
rest, so this is the knob that bears on what is left.

It was measured again after the search was changed, on a hundred tuning tables:

| what a longer push is made to cost | tables separated of 100 | glasses it gave room to | glasses broken | arm seconds a table |
|---|---|---|---|---|
| **0.1 a millimetre, problem 3's figure, kept** | **48** | **+136** | 3 | 25.7 |
| 0.3 a millimetre | 33 | +93 | 2 | 20.9 |
| 0.1, and no push longer than 60 mm | 39 | +120 | 2 | 25.2 |

**Both ways of shortening the pushes lose nine to fifteen tables of a hundred to
save one glass**, which is not a trade worth making: a table left crowded scores
nothing either, and the share counts every glass on it. The same knob measured on the search as it stood before
gave the same shape — at 0.5 it separated ten and eleven tables of forty against
fourteen and seventeen at 0.1 — so the pessimism has not changed the trade. What
the pessimism changed is how many glasses are broken at the price that was
already there: nine of two hundred tuning tables, where the same price used to
break thirty-one.

There is a general lesson in that about a queue budget, and it has since been
paid for twice. A setting chosen on a sample of tables is chosen for the
difficulty of that sample — and worse, the sample above gives every table as
much arm time as it wants, while the score gives fifteen arm minutes for fifty
tables. Those are different questions: one asks whether a table *can* be
separated and the other how much gets done before the clock stops, and a change
that trades time for thoroughness wins the first and loses the second. Two later
changes to this solution were chosen on the unclocked sample and lost on the
queue before that was noticed. The solution now has a `select` command that
walks fifty tables below the held-out line under the real budget, three times,
and choices are made on three such bands rather than on the unclocked hundred.

**The rung this page used to name has been tried twice and dropped twice.** It
was to put the geometry reference's five-millimetre test push back in front of
the model's long pushes, so that the one thing the model is worst at is measured
rather than predicted. Built and measured on forty tuning tables, it cut the
glasses broken from four to one — and cut the tables separated from seventeen to
**eight**, because a glass that does not keep up with a probe is then left alone
for the rest of the table.

It was then tried again in a narrower form, which is the form that should have
worked: test a glass only when the three copies of the model *disagree* about
the push, since a push they disagree about topples a glass 17% of the time
against 6% for the search's own picks. Measured at three thresholds on nine
clocked walks, it cost between one and four tables a walk and saved **no
glasses at all**. The reason is the measurement that governs this whole problem:
a five-millimetre test says whether a glass slides a little, and the tipping
rule can predict no glass in this cell, so a short test tells you nothing about
a long push. The reference survives that by freeing a glass over a run of small
pushes judged one at a time; this solution makes one long push.
[`what-changed.md`](../what-changed.md) holds all of those numbers.

## Where it sits beside the others

| fifty tables offered from 10,000 | 1 geometry | 2 ranked geometry | **4 world model** | 5 model as it downloads |
|---|---|---|---|---|
| Tables attempted | 26 | 25 | **39** | 11 |
| Tables separated | 10 | 7 | **14** | 1 |
| Tables failed by a topple | **0** | **0** | 5 | **0** |
| Glasses it gave room to | +25 | +19 | **+33** | +2 |
| Share pickable | **0.627** | 0.582 | 0.550 | 0.439 |
| Glasses broken | **0** | **0** | 5 | **0** |
| Thinking an answer | 15 ms | 15 ms | **11 ms** | 280 ms |

Read across the row of tables separated and then across the row of shares. This
solution separates four more tables than anything else here and gives room to
eight more glasses, and it holds the third share rather than the first, because
it reaches so much further down the queue that the tables it leaves crowded are
counted against it — and, after this round, because five tables a walk are
forfeited for a broken glass. The two columns on either side of it are the two
ends of this problem: geometry that is slower and finishes what it starts, and a
borrowed model that is safe and frees a glass or two by accident.

**The one thing this solution is plainly best at is thinking.** Eleven
milliseconds an answer, against the geometry's fifteen, where in problem 3 the
same method thought four times *longer* than the geometry it was compared with.
The geometry walks seventy-two directions by seventy-five push lengths in plain
Python for every crowded glass; the search asks three small networks about eight
hundred candidates in one array and then checks a handful of corridors. Arm time
is the budget, so this buys nothing on the card — but it answers the question of
whether a world model can be afforded in a cell like this one, and the answer is
yes.

## What to take from it

**A learned model of the physics is affordable here, and it separates more
tables than anything else this problem has.** It separates fourteen of the
thirty-nine tables it reaches against the geometry's ten of twenty-six, gives
room to +33 glasses against +25, and a table it separates costs it forty per
cent less arm time. Cut to the twenty-six tables both of them reached, it
separates ten against ten, so the reach is the whole of its advantage.

**What made the difference was not the model but how it is used.** For a long
time the fitted file did not change at all: the same thirteen hours of arm time,
the same fourteen millimetres of error at the median. What changed is that the
search stopped taking its model at its most optimistic. Reading the least
favourable of three copies, pricing a predicted chance of toppling rather than
merely obeying a limit, and refusing a push whose hand would sweep a neighbour
took the glasses broken on a walk from eight to one and raised the separations
from eleven to fourteen at the same time. **A search over a model is a place
where being careful costs nothing and buys both halves of the card.**

**Then the data was doubled, and that is the honest second half of the story.**
It improved the model where a model can be improved — a millimetre at the median
and three at the ninetieth on where a glass lands — and it made the model less
easily alarmed about toppling, which a fixed caution threshold turns into more
broken glasses. Pairing it with a tenfold cost for a missed topple recovers the
refusal, and on a hundred and fifty tables below the held-out line the pair
separates more tables and breaks fewer glasses than the fit before it. On the
forty held-out tables it breaks five a walk instead of one and a half. One band
of forty disagrees with three bands of fifty, and the change is kept because the
bands below ten thousand are where choosing is allowed to happen.

**What is left is not more of this data.** Three attempts to buy the breakages
back failed in the same way: a tighter threshold cannot refuse a push the model
gives no chance at all, a five-millimetre test cannot predict a fifty-millimetre
push in a cell where the tipping rule predicts nothing, and collecting the
pushes the copies disagree about teaches the model about pushes it will then be
no better at refusing. What this solution needs next is a *separate* model of
toppling, fitted and calibrated as its own question, rather than one more output
of a network whose loss is dominated by where the glass lands.

**And the geometry's advantage is still the same one.** It finishes what it
starts and breaks nothing at all, which gives it the best share. What it cannot
do is reach the end of the queue.

## Where to go next

- [The examiner](../the-examiner.md) — the tables, the arm's clock, the camera
  on the wrist, the one budget for the queue, and every line on the card.
- [The problem](../problem.md) — what is on the table, what goes in, what comes
  out, and what "done" means here.
- [The same method in problem 3](../../03-push-glasses-apart/solutions/04-a-world-model.md)
  — what a forward model is, how the search works, and why three copies of one
  network measure ignorance.
- [The solution's own folder](../../../04-clear-the-table/04-a-world-model/) —
  what is borrowed, what it cost to fit, the tuning band, and every per-table
  row quoted above.
- [Known gaps](../../known-gaps.md) — the limits this project knows it has.

---

← [Solution 2 — geometry generates, a model ranks](02-geometry-ranked.md) ·
[The examiner](../the-examiner.md) ·
[Solution 5 — a borrowed model, as it downloads](05-smolvla-as-it-downloads.md) →
