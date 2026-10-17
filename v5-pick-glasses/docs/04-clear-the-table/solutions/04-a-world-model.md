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

| fifty tables offered from 10,000 | the geometry reference | **this, the model** | this, before the search was changed |
|---|---|---|---|
| Tables attempted | 26 | **40** (40, 40, 41) | 32 |
| Glasses on those tables | 102 | 160 (160, 160, 164) | 125 |
| Tables separated, nothing broken | 10 | **14** (11, 14, 15) | 11 |
| Tables failed by a topple | **0** | 1 (0, 1, 2) | 7 |
| Tables left unfinished | 16 | 25 (29, 25, 24) | 15 |
| Glasses pickable at the end | 64 | 98 (94, 100, 98) | 70 |
| Of those, had room already | 39 | 59 (61, 59, 59) | 39 |
| Glasses it gave room to | +25 | **+39** (+33, +41, +39) | +29 |
| Share of glasses pickable | **0.627** | 0.598 (0.588, 0.625, 0.598) | 0.560 |
| Glasses broken | **0** | 1 (0, 1, 2) | 8 |
| It declared a table finished | 24 of 26 | 39 of 40 (39, 39, 37) | 24 of 32 |
| …while the table was still crowded | 14 | 25 (28, 25, 22) | 13 |
| Arm seconds for a table it separated | 43.6 | **25.4** (24.0, 25.4, 28.5) | 26.7 |
| Thinking an answer | 15 ms | **10 ms** | 6 ms |
| Pushes the cell's interlock refused | 0 | 0 | 0 |

**Three readings come out of that card.**

The first is that **the saving it was ported to make is real.** A table it
separates costs it 25.4 arm seconds against the reference's 43.6. That number
is worth more than it looks, because it is averaged over tables that were
actually finished, so a table cut short by a falling glass cannot flatter it.
The saving is about forty per cent off a win, and it is the whole of the extra
reach: forty tables attempted against twenty-six.

The second is that **it is the best separator measured on this problem.**
Fourteen tables against the reference's ten, with the three walks giving 11, 14
and 15 while the reference is deterministic and gives 10 every time. Before the
search was changed the three walks gave 12, 8 and 11 around a median of 11,
which is a win smaller than its own spread and therefore not a win at all. It is
also furthest ahead on glasses given room: +39 against +25, over fourteen more
tables.

The third is that **its share of pickable glasses is still a little below the
geometry's**, 0.598 against 0.627, and that the reason has changed. It used to
be the breakages. It is now the tables left crowded: this solution reaches
fourteen more tables than the geometry does, and the share is taken over every
glass on every table attempted, so the tables it reached and did not finish are
counted against it. The two sections after this one separate those two things.

**One more comparison is worth making, because the card above compares walks of
different lengths.** A faster solution reaches further down the queue, and the
tables it reaches there are not the tables the reference was scored on. Cut both
walks to the twenty-six tables the reference reached, which the comparison page
does for every row, and this solution separates eleven tables against ten, frees
twenty-nine glasses against twenty-five, and breaks nothing. Its spread on those
tables is eight to twelve separated, which holds the reference's ten. So the
fair statement is that on the same tables it is level or a little ahead, and that
its clear advantage is reaching half again as many tables in the same quarter of
an hour.

## Why breaking glasses used to cost it the win, and what is left of that

A table where a glass went over earns nothing at all. Not a reduced amount:
nothing. Every glass on it leaves the pickable count while all of them stay in
the total, including the glasses that already had room before the arm arrived.
The examiner is explicit about why — if a lost table still paid out for its
other glasses, a hard and risky shove would be close to free, and a method
could gamble its way up the card.

That rule used to decide this solution's score. Of the 125 glasses it met on a
walk, 19, 30 and 27 stood on tables it broke a glass on, which is between a
seventh and a quarter of everything it touched; doing nothing at all on those
tables would have been worth about seven points of share, and seven points was
the whole of the gap to the geometry. **The breakages were not what stopped it
winning by more. They were what stopped it winning.**

They are now one table in a walk, and the same arithmetic says so:

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Share of glasses pickable, as scored | 0.588 | 0.625 | 0.598 |
| …had the broken tables merely been left crowded | 0.588 | 0.638 | 0.616 |
| …had they been separated instead | 0.588 | 0.656 | 0.646 |

The first walk broke nothing at all, so its three numbers are one number. In the
other two, doing nothing on the tables it broke a glass on would have been worth
one or two points of share. **So breakage is no longer what holds this solution
back.** The bottom row is the interesting one instead: separating every table it
broke a glass on would bring it to about the geometry's 0.627 at best, because
what is really left is twenty-five tables reached and left crowded.

## Which tables it breaks, and which it separates

The per-table rows are worth reading, because the breakages used to sit in one
identifiable part of the queue and now they do not sit anywhere.

| tables | walks | separated | failed by a topple | glasses given room | glasses broken |
|---|---|---|---|---|---|
| The first eighteen, 10,000 to 10,017 | 54 | 6, 10, 9 of 18 | **0** | +18, +23, +23 | **0 of 204** |
| 10,018 to 10,025 | 24 | 2, 2, 2 of 8 | 0, 1, 0 | +5, +7, +6 | 0, 1, 0 of 102 |
| 10,026 onwards | 43 | 3, 2, 4 | 0, 0, 2 | +10, +11, +10 | 0, 0, 2 of 178 |

**Three glasses went over in three walks of forty tables, on three different
tables, and no table breaks a glass in more than one walk.** They are tables
10,023, 10,027 and 10,035. The first eighteen tables were attempted fifty-four
times without a single breakage.

That is a different shape from the first measurement of this solution. Then,
eight glasses went over, tables 10,018 to 10,025 broke one in nearly every walk,
and that stretch is the hard part of this queue — the geometry reference walks it
with time to spare, separates **none** of those eight, and gives room to
**one** glass in total. Being willing to act where the geometry declines used to
cost three or four glasses there. It now costs one glass in one walk of three,
and still separates two of the eight every time.

Lining the two solutions up table by table over the twenty-six tables the
reference reached:

- The model breaks a glass on **one** of them, in one walk of three.
- It separates six tables the reference never separates in any walk, and all
  six are tables the reference leaves crowded.
- The reference separates three tables the model never separates. On a table
  where a safe push exists and the geometry can see it, the two make much the
  same push, and this one is a little more willing to leave a glass that two
  pushes have not freed.
- It separates seven of the twenty-six in every walk and thirteen in at least
  one, against the reference's ten every time. The spread between those two
  numbers is the price of a search that draws its candidates from noise.

**So the extra wins and the remaining breakages still come out of the same
decision** — being willing to act where the geometry finds no clear corridor —
but they no longer come out of the same tables, and the breakages are no longer
concentrated anywhere.

## What the model believed about the pushes that broke a glass

This page used to end its argument here with a question it could not answer: is
the model wrong, or does the search trust it too far? Both readings fitted the
rows equally well, and what would have settled it was a record of what the model
believed about every push it made, beside what the table then did. Nothing saved
that. It is saved now.

**The answer is that the model was confident and wrong.** On the twenty tuning
tables, where four glasses went over, the four pushes that put them over were
given a chance of toppling something of **one in ten thousand or less**. The
copies of the model did not disagree about them, so the pessimism that removed
most of the breakages cannot help here: there was no disagreement to charge for.

**And they were long.** The four pushes that broke a glass travelled 52 mm at
the median; every other push made on those tables travelled 19 mm. A long push
is where this model has the least data and the most to be wrong about, and it is
also where being wrong does the most damage, because the glass has further to go
and more neighbours to meet on the way.

That is a statement about the *data* rather than about the search, and it is the
first time this solution's failures have pointed there. The next rung is
therefore more pushes in the band where it is weakest, which costs arm time in
the simulator and nothing in the cell.

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

There is a general lesson in that about a queue budget, and it is worth keeping
even though the setting did not move. A setting chosen on a sample of tables is
chosen for the difficulty of that sample, and a solution fast enough to reach
past the sample is then measured on tables the setting was never weighed
against. This solution now reaches forty tables of fifty, which is further
past its own tuning band than any other solution here gets.

**The rung this page used to name has been tried and dropped.** It was to put
the geometry reference's five-millimetre test push back in front of the model's
long pushes, so that the one thing the model is worst at is measured rather than
predicted. Built and measured on forty tuning tables, it cut the glasses broken
from four to one — and cut the tables separated from seventeen to **eight**,
because a glass that does not keep up with a probe is then left alone for the
rest of the table. Once the search was pessimistic it bought nothing that
pessimism had not already bought.
[`what-changed.md`](../what-changed.md) holds those numbers.

## Where it sits beside the others

| fifty tables offered from 10,000 | 1 geometry | 2 ranked geometry | **4 world model** | 5 model as it downloads |
|---|---|---|---|---|
| Tables attempted | 26 | 25 | **40** | 11 |
| Tables separated | 10 | 7 | **14** | 0 |
| Tables failed by a topple | **0** | **0** | 1 | **0** |
| Glasses it gave room to | +25 | +19 | **+39** | 0 |
| Share pickable | **0.627** | 0.582 | 0.598 | 0.400 |
| Glasses broken | **0** | **0** | 1 | **0** |
| Thinking an answer | 15 ms | 15 ms | **10 ms** | 279 ms |

Read across the row of tables separated and then across the row of shares. This
solution separates four more tables than anything else here and gives room to
fourteen more glasses, and it still holds the second share rather than the
first, because it reaches so much further down the queue that the tables it
leaves crowded are counted against it too. The two columns on either side of it
are the two ends of this problem: geometry that is slower and finishes what it
starts, and a borrowed model that is safe now and does nothing.

**The one thing this solution is plainly best at is thinking.** Ten
milliseconds an answer, against the geometry's fifteen, where in problem 3 the
same method thought four times *longer* than the geometry it was compared with.
The geometry walks seventy-two directions by seventy-five push lengths in plain
Python for every crowded glass; the search asks three small networks about eight
hundred candidates in one array and then checks a handful of corridors. Arm time
is the budget, so this buys nothing on the card — but it answers the question of
whether a world model can be afforded in a cell like this one, and the answer is
yes.

## What to take from it

**A learned model of the physics is affordable here, and it is now the best
answer this problem has.** It separates fourteen tables of the forty it reaches
against the geometry's ten of twenty-six, gives room to +39 glasses against
+25, and a table it separates costs it forty per cent less arm time. Cut to the
twenty-six tables both of them reached, it separates eleven against ten and
breaks nothing, so the lead on the same tables is small and the lead in reach is
large.

**What made the difference was not the model but how it is used.** The fitted
file did not change: the same thirteen hours of arm time, the same fourteen
millimetres of error at the median. What changed is that the search stopped
taking its model at its most optimistic. Reading the least favourable of three
copies, pricing a predicted chance of toppling rather than merely obeying a
limit, and refusing a push whose hand would sweep a neighbour took the glasses
broken on a walk from eight to one and raised the separations from eleven to
fourteen at the same time. **A search over a model is a place where being
careful costs nothing and buys both halves of the card.**

**What is left is the data, and the record now says so.** The few glasses it
still breaks go over on pushes the model was confident about and that were three
times longer than the pushes that broke nothing. That is where the fitted set is
thinnest, and it is a reason to collect more long pushes rather than to search
differently again.

**And the geometry's advantage is now a narrow one.** It finishes what it
starts and breaks nothing at all, which still gives it the best share. What it
cannot do is reach the end of the queue.

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
