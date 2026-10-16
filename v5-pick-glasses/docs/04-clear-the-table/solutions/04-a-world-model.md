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

The measurement says it does buy that, and then loses more than it bought
somewhere else. **It separates more tables than any other solution so far, and
it is the only one that puts glass on the floor.** A table that loses a glass
is worth nothing at all, so the seven tables a walk that end that way are not a
discount on the score — they are removed from it. By the end of this page you
will know:

- how this solution was put to a problem with no view of the whole table;
- what the held-out queue measured, and what the two different bands of tables
  in its folder each answer;
- why it reaches further down the queue than the geometry does;
- which tables it breaks glasses on, and why those are exactly the tables its
  extra wins come from;
- what the saved numbers can and cannot say about *why* a push it believed was
  safe was not.

Read [the examiner](../the-examiner.md) first. It defines what a solution is
shown, what it may answer, why saying "done" is part of the job, and how a walk
of the queue is marked.

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
| Second round, the search's own pushes | 300 | 1,482 | 2.4 hours |
| Validation, never fitted on | 150 | 658 | 1.2 hours |

**Thirteen hours of the arm, where problem 3 collected twice as many pushes for
nothing at all.** That is the clearest single consequence of taking the
overhead camera away. A push in problem 3 cost one call to a camera that saw
the whole table. Here the arm has to walk the ring before it knows where
anything is, and walk to a stand again whenever the glass it pushed is hidden
from where it is standing, so a collecting table gives back four or five
pushes for about twenty-eight arm seconds.

On the 658 validation pushes, made on tables nothing was fitted on, 254 really
moved a glass. The model puts those 14 mm from where they land at the median
and 50 mm out at the tenth-worst in a hundred. Problem 3's model, fitted on
five times the data, manages 6.5 mm and 39 mm. The topple filter the search
works at catches 57 of the 70 pushes that really put a glass over, and flags
116 of the 588 that did not. **Those two sentences are the whole character of
this solution, and the rest of this page is what they cost on a real queue.**

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

| fifty tables offered from 10,000 | the geometry reference | **this, the model** |
|---|---|---|
| Tables attempted | 26 | **32** (32, 33, 32) |
| Glasses on those tables | 102 | 125 (125, 130, 125) |
| Tables separated, nothing broken | 10 | **11** (12, 8, 11) |
| Tables failed by a topple | **0** | 7 (5, 8, 7) |
| Tables left unfinished | 16 | 15 (15, 17, 14) |
| Glasses pickable at the end | 64 | 70 (70, 64, 71) |
| Of those, had room already | 39 | 39 (41, 39, 38) |
| Glasses it gave room to | +25 | **+29** (+29, +25, +33) |
| Share of glasses pickable | **0.627** | 0.560 (0.560, 0.492, 0.568) |
| Glasses broken | **0** | 8 (6, 8, 8) |
| It declared a table finished | 24 of 26 | 24 of 32 (25, 24, 24) |
| …while the table was still crowded | 14 | 13 (13, 16, 13) |
| Arm seconds for a table it separated | 43.6 | **26.7** (26.9, 24.1, 26.7) |
| Thinking an answer | 15 ms | **6 ms** |
| Pushes the cell's interlock refused | 0 | 0 |

**Three readings come out of that card, and they point in different
directions.**

The first is that **the saving it was ported to make is real.** A table it
separates costs it 26.7 arm seconds against the reference's 43.6. That number
is worth more than it looks, because it is averaged over tables that were
actually finished, so a table cut short by a falling glass cannot flatter it.
Its own folder could not show this on the band of tables it was tuned on: there
the figure quoted was arm seconds over *all* tables, and most of the apparent
saving there was tables that ended early. The queue priced the same thing
honestly, and the honest price is about forty per cent off a win. That saving is
the whole of the extra reach: 32 tables attempted against 26.

The second is that **it is, by a small margin, the best separator measured so
far.** Eleven tables against the reference's ten. The margin should be read with
the examiner's own rule in mind: the three walks gave 12, 8 and 11, while the
reference is deterministic and gives 10 every time. A method that wins by less
than its own spread has not been shown to win, so the right statement is that it
is level with the geometry on separations and ahead of it on glasses given room,
+29 against +25, while reaching six more tables.

The third is that **its share of pickable glasses is below both of the geometry
solutions'**, 0.560 against 0.627. That is the one the rest of this
page is about, because it is not a worse push anywhere. It is the eight broken
glasses, and the twenty-seven glasses that were standing on the tables those
breakages happened on.

## Why breaking glasses costs it the win it otherwise had

A table where a glass went over earns nothing at all. Not a reduced amount:
nothing. Every glass on it leaves the pickable count while all of them stay in
the total, including the glasses that already had room before the arm arrived.
The examiner is explicit about why — if a lost table still paid out for its
other glasses, a hard and risky shove would be close to free, and a method
could gamble its way up the card.

Here is what that rule costs this solution. Of the 125 glasses it saw on a
walk, 19, 30 and 27 of them were standing on tables it broke a glass on, which
is between a seventh and a quarter of everything it touched.

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Share of glasses pickable, as scored | 0.560 | 0.492 | 0.568 |
| …had those tables merely been left crowded | 0.616 | 0.577 | 0.648 |
| …had those tables been separated instead | 0.664 | 0.662 | 0.720 |

The middle row is the interesting one, and it is not a hypothetical about
pushing better. It is the score this solution would have had if, on those seven
tables, it had simply done nothing at all. Doing nothing on them would have
been worth about seven points of share, which is the whole of the gap to the
geometry reference's 0.627. **The breakages are not what stops it from winning
by more. They are what stops it from winning.**

## Which tables it breaks, and which it separates

The per-table rows settle this question with unusual clarity, because the
breakages are not scattered over the queue. They sit entirely in one part of
it.

| tables | walks | separated | failed by a topple | glasses given room | glasses broken |
|---|---|---|---|---|---|
| The first eighteen, 10,000 to 10,017 | 54 | 9, 6, 7 of 18 | **0** | +22, +19, +22 | **0 of 68** |
| 10,018 to 10,025 | 24 | 2, 2, 2 of 8 | 3, 3, 4 | +8, +6, +8 | 4, 3, 4 of 34 |
| 10,026 onwards | 19 | 1, 0, 2 | 2, 5, 3 | +2, +1, +5 | 2, 5, 4 |

**On the first eighteen tables it broke nothing, in fifty-four attempts at
them.** All twenty breakages across all three walks happened on table 10,018 or
later. That is not a coincidence of the clock running low, because no solution
in problem 4 reads how much time is left, and the budget still held more than
five minutes when the first breakage happened.

It is a property of those tables, and the geometry reference proves it
independently. The reference is deterministic and walks the same list, and it
reached tables 10,018 to 10,025 with room to work: on six of the eight it said
the table was finished rather than being stopped by the clock. On those eight
tables it separated **none**, and gave room to **one** glass in total. On two of
them it walked the ring, found no push worth making at all, and said the table
was finished after eight seconds. On the eighteen tables before them it separated
ten and gave room to twenty-four. So the queue happens to contain an easy
stretch followed by a hard one, and "hard" here has a precise meaning: the
crowding is such that the geometry can find no push whose corridor for a
139 mm hand is clear of every neighbour.

That is the distinction the question was asking for. Lining the two solutions up
table by table over the twenty-six tables both of them reached:

- The model broke a glass on five of them. The reference separated **none** of
  those five.
- The model separated five tables the reference never separates in any walk.
  All five are tables the reference leaves crowded.
- The model never once separates three tables that the reference does separate.
- There is **no table** where the reference succeeds and the model breaks a
  glass.

**So the breakages and the extra wins come out of the same decision.** On a
table where a safe push exists and the geometry can see it, this solution makes
much the same push and finishes much the same table, a little cheaper and a
little less often. On a table where the geometry declines, it pushes anyway.
Two of those eight tables it wins in every single walk; three or four of the
eight end on the floor. Table 10,023 is the clearest case: the reference sweeps
it, finds nothing it is willing to do, and says so in eight seconds; the model
attacks it and loses a glass in two of three walks.

Being willing to act where the geometry declines is not a fault. It is the only
reason this solution separates more tables than the geometry, and in problem 3
it was the whole of its advantage. Problem 4 simply charges a different price
for being wrong about it.

## Is the model wrong, or does the search trust it too far?

This is the question a reader should ask next, and the saved rows answer part of
it and not all of it. What follows separates the two.

**Two things the rows do settle.**

The cell's safety interlock refused nothing, in all three walks. The interlock
is the cell's refusal to drive the hand into a glass that the public tipping
rule says would tip rather than slide, and it fired zero times, because this
solution runs that same test itself and drops such a push before answering. So
every one of the eight broken glasses came from a push that the model called
safe *and* that the arithmetic anybody could do also called acceptable. Nothing
was bypassed, and nothing in the cell was in a position to save it.

The breakages are not a stale belief, either. Nine of the twenty happened on
the ninth answer of the table — eight answers to walk the ring of stands, and
then one push. That is the push made on the most complete and freshest
information this solution ever has about a table, immediately after looking at
it from all eight sides. Seventeen of the twenty happened within the first
twenty answers. So this is not error piling up over a long table; it is the
first considered push.

**One thing the rows strongly suggest.** On tables nothing was fitted on, the
filter at one chance in a hundred let through 13 of the 70 pushes that really
toppled something, while passing 472 of the 588 that did not. So of every
hundred pushes the filter passes in that validation set, about three put a glass
over. A table here takes only a handful of pushes, so three in a hundred per
push should break a glass on well under a tenth of tables. The observed figure
on the hard stretch is about half of them. The pushes the search chooses are
therefore several times more dangerous than the pushes the same filter passed
when the pushes were drawn at random.

That is what a search over a model's own estimates does. It does not sample the
model's opinions, it maximises over them, so it lands by preference exactly
where the model is most optimistic. The familiar name for it is the winner's
curse: pick the best of many noisy estimates and you have mostly picked the
largest error.

**What the rows cannot settle.** There is a second reading that fits them just
as well. On the hard tables there may be no safe push at all, so the model is
not being exploited by the search — it is being asked a question whose true
answer is "every candidate is dangerous", and a model with a leaky filter will
pass some of them however they are chosen. The two readings call for different
fixes, and the per-table rows cannot tell them apart, because a row records the
outcome of a table and not the push that ended it.

**The measurement that would settle it** is to record, for every push this
solution answers with, the model's predicted topple chance and its predicted
movements, beside what actually happened. Two numbers come out of that
immediately: how often a push the search *chose* topples something, against the
three in a hundred measured on randomly drawn pushes, and whether the pushes
that topple are ones the model was confident about or ones its three copies
disagreed over. Grouped by whether the geometry reference would have made any
push on that table, it separates the two readings cleanly. Nothing in the run
saves that today, and it costs no arm time to save, because it is all on the
laptop's side of the fence.

## The knob that would trade some of it back, and why it was not turned

The search pays a small price for every millimetre it pushes, and that price is
the setting that trades room against arm time and against risk. A longer push
makes more room, takes longer, and is more likely to put something over. It was
chosen on forty tuning tables, where raising the price from the inherited 0.1 to
0.5 dropped the glasses over from four and six to one and three, and dropped the
tables separated from fourteen and seventeen to ten and eleven, out of forty.

It is worth being clear that the setting was chosen honestly and still cost it.
On those tuning tables the cheap setting was better by *both* readings: it
separated more tables and it also left a higher share of glasses pickable, 0.61
to 0.66 against 0.53 to 0.56, breakages and all. The held-out queue returned
0.560 for the same setting. Nothing was tuned on the wrong band and nothing was
measured twice. What happened is that the queue reaches further than the tuning
band went, into a stretch of tables where the same willingness to push buys
fewer separations and more floor.

That is a general lesson about a queue budget rather than about this solution. A
setting chosen on a sample of tables is chosen for the difficulty of that
sample. A solution fast enough to reach past it is measured on tables the
setting was never weighed against.

**The next rung is not a better model.** It is to put the geometry reference's
five-millimetre test push back in front of the model's long pushes, so that the
one thing the model is worst at is measured rather than predicted, and let the
model choose everything else. The test push costs a second or two of arm time,
against a table and every glass on it. That is a different solution from this
one and should be built as one.

## Where it sits beside the others

| fifty tables offered from 10,000 | 1 geometry | 2 ranked geometry | **4 world model** | 5 model as it downloads |
|---|---|---|---|---|
| Tables attempted | 26 | 25 | **32** | 15 |
| Tables separated | 10 | 7 | **11** | 0 |
| Tables failed by a topple | **0** | **0** | 7 | 14 |
| Glasses it gave room to | +25 | +19 | **+29** | −1 |
| Share pickable | **0.627** | 0.582 | 0.560 | 0.018 |
| Glasses broken | **0** | **0** | 8 | 20 |
| Thinking an answer | 15 ms | 15 ms | **6 ms** | 776 ms |

Read across the row of glasses broken and then across the row of shares. The
two solutions that break nothing hold the two best shares, and they are the two
that only ever make a push they can justify from geometry. This solution gives
more glasses room than either of them and still scores below both. The borrowed
model in the last column is a different failure altogether and has
[its own page](05-smolvla-as-it-downloads.md).

**The one thing this solution is plainly best at is thinking.** Six
milliseconds an answer, against the geometry's fifteen, where in problem 3 the
same method thought four times *longer* than the geometry it was compared with.
The geometry walks seventy-two directions by seventy-five push lengths in plain
Python for every crowded glass; the search asks three small networks about eight
hundred candidates in one array. Arm time is the budget, so this buys nothing on
the card — but it answers the question of whether a world model can be afforded
in a cell like this one, and the answer is yes.

## What to take from it

A learned model of the physics is affordable here, and it does buy what it was
expected to buy: a win costs it forty per cent less arm time than the geometry's
win, so it gets six tables further down the same list in the same fifteen
minutes.

It is also the first solution in this problem to meet the no-free-breakage rule
head on, and the rule is what decides its score. Eight glasses, over seven
tables, on a stretch of the queue where the geometry achieves nothing at all,
remove enough from the card to turn the best separations and the best gain
measured so far into a share below both of the geometry solutions'.

The honest summary is that this is a method with the right instinct and no
measurement behind it at the one moment that matters. It is willing to act where
the geometry gives up, which is where the remaining tables are; and the thing it
substitutes for the geometry's test push — a prediction, right fifty-seven times
in seventy — is not good enough to act on when being wrong costs a whole table.

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
