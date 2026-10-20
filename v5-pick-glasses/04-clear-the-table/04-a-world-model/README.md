# Problem 4 — the learned way, with no view of the whole table

Problem 4's task is problem 3's: some glasses stand too close together for the
gripper to get round them, and the arm pushes them apart. Two things are taken
away. The camera above the table is gone — the arm carries its own — and
nothing hands a push over one at a time, so the solution runs until it says it
is finished.

This is [problem 3's solution 4](../../03-push-glasses-apart/04-a-world-model/)
ported to that. A small network learns what a push does to a table, from pushes
really made in the physics engine, and a search asks it about a few thousand
candidate pushes before the arm moves. It is the only learned solution here
that borrows no foundation model: everything in this folder was fitted on this
cell, on the processor, in nine minutes of laptop time — and thirteen hours of
the arm's, which is the number that matters in problem 4 and is where most of
what follows comes from.

## What is borrowed and what is new

| | |
|---|---|
| `tour.py` in [problem 4's solution 1](../01-one-fixed-nudge/) | **borrowed.** Where to stand to see the table, and in what order to go there. |
| `remembered.py` | **borrowed.** What has been seen, merged across looks. |
| `jaw_paths.py` | **borrowed.** A push written out as the jaw's own waypoints. |
| `nudge.py` | **borrowed, and subclassed.** The whole loop: sweep, decide, push, look again, sweep, say done. `learned.py` replaces its deciding, and two smaller things that follow from the deciding: which glasses are forgotten after a push, and (under `--predicting`) whether the push is looked at. |
| `plan.py` in problem 3's solution 1 | **borrowed for two things only:** the touchdown point outside a glass's widest part, and the lean bound on how deep the fingertips may be driven. Its chooser is not used. |
| `encoding.py` | **new.** What the model is shown about a push, and what it is asked to predict. |
| `push_model.py` | **new.** Three copies of a small network. |
| `collect.py` | **new.** Pushes really made on training tables, and what the camera saw happen. |
| `bench/keeping_clear.py` | **borrowed.** The clearance check every solution in this problem runs over its own answer. The search asks it of the pushes it is about to prefer. |
| `search.py` | **new.** The cross-entropy search over candidate pushes. |
| `learned.py` | **new.** The reference's loop with the model deciding. |

`borrowed.py` holds the whole debt on one page, as `bench/partners.py` does for
problem 3. Nothing here is called `plan.py`, `run.py`, `features.py` or
`model.py`, and that is not a preference: those names are already taken by
problem 3's solution 1, by the bench, and by what problem 4's solution 2
registers, and a file here with one of them would shadow the file it is meant
to be borrowing from.

## How it works

```
1. sweep the ring of stands ──▶ one belief about the table
2. for every glass still crowded: search pushes ──model──▶ best push
3. make that push ──▶ look again ──▶ back to 2
   nothing worth pushing ──▶ sweep the ring again ──▶ say done
```

Only step 2 uses the model. Everything else is the geometry reference's, and
the reference expected to be reused this way: `_choose` is a method there
rather than a line inside its loop, "because the next solution in this problem
is this same loop with a different chooser".

**The model.** Three copies of a three-layer network, 128 wide, trained from
different starting weights on the same pushes. Where the copies disagree, the
model has not seen a push like this one, and the search takes the worst of
their topple chances rather than the average.

- In, 26 numbers: the pushed glass's height, widest width and foot; the push —
  how far across the glass the jaw meets it, how far it pushes, and **how far
  it reaches in before it expects to touch**; and where up to four other
  glasses stand and how big they are. Everything is measured along the push and
  across it, so a push north and the same push east are one example.
- Out, 11 numbers: where the pushed glass moves, where each other glass moves,
  and the chance that something goes over.

**The push has a fourth number here that it does not have in problem 3, and it
is the whole difference between the two problems' actions.** Problem 3 hands
the bench a `Push` and the bench feels its way in: it creeps forward from the
touchdown point until its force sensor finds the glass, and pushes from
wherever that turned out to be. Problem 4 hands over a chunk of waypoints, and
a chunk cannot feel. The jaw meets a glass at the jaw's own height, where a
stemmed glass is its stem, so that distance is 10 to 30 mm and has to be known
before the path is written. The geometry reference finds it out by poking —
drive five millimetres deeper, look, see whether the glass moved, repeat — and
pays arm seconds for every round. Here it is an input the model has an opinion
about.

**The map is the only thing written down.** Where a glass may stand, and how
far the arm can reach. There is no friction value and no tipping formula in this
folder — with one exception, kept deliberately: how deep the fingertips may be
driven is still bounded by the reference's own lean bound. Problem 3's solution
4 has no such rail and toppled twenty glasses in fifty tables. Here a toppled
glass costs the whole table and every glass on it, and reaching too deep is the
one mistake a camera cannot see coming, because a glass that has not been
touched and a glass that is leaning both sit still.

**Choosing a push.** For each crowded glass, the cross-entropy method tries 800
pushes over three rounds, varying the heading, where across the glass to push,
how far, and how far to reach in. A push is dropped if

- any copy of the model gives it more than a 0.01 chance of toppling something
  — problem 3's own figure, kept — on the table as measured or on two copies of
  it shifted by the camera's own error;
- a glass it moves would land outside the glass zone, or the jaw would leave
  the arm's reach, as **any** copy of the model sees it;
- the model predicts a movement longer than the push itself, which is the model
  answering outside what it has seen;
- the hand would sweep a glass it was not aimed at on the way in. The model is
  asked where the glasses end up and never asked what the hand passes through,
  so this is the geometry reference's own corridor rule, written out over whole
  arrays so that hundreds of candidates can be asked at once.

The rest are scored by how much room the table would still be short of
afterwards, plus a price per millimetre pushed and a price for the chance of
toppling something. **Every one of those readings is the model's least
favourable copy and not the average of the three**, and that is the point: a
search that asks a model about a few thousand pushes and takes the best answer
is choosing the largest error, so where the copies disagree a candidate has to
cost more rather than less. The cheapest push over all the glasses is made,
once the clearance check every solution here can run has passed it and the
cell's own interlock would not refuse it. Both are asked before the push is
answered, because a refused path moves the arm nowhere, so the solution would be
shown the same table back and would spend that glass's four tries proposing the
same push. Then the arm looks again and the search runs afresh.

**The three prices and the pessimism were added after the first walk of the
held-out queue**, which this solution lost seven tables and eight glasses on.
[`what-changed.md`](../../docs/04-clear-the-table/README.md) measures what
each of them bought.

## What I expected before measuring

Written down before the first measured run, because a prediction made
afterwards is not one.

Problem 3's solution 4 beat its geometry reference on glasses and lost to it on
breakage. **In problem 4 looking costs arm time, so I expected the same trade
plus a saving the model cannot make in problem 3:**

1. **Fewer arm seconds a table than the reference**, because the ranging push
   and the test push are motion — the reference's own way of finding out, with
   the arm, what this model is asked to predict — and taking them out replaces
   seconds of pushing with milliseconds of thinking.
2. **A higher share of the arm time spent looking**, above the reference's
   figure, because it is the pushing half that shrinks and the two sweeps of
   the ring stay exactly as they were.
3. **More glasses made pickable**, because the search is not bound by the
   reference's rule that the hand's corridor must be clear of every neighbour:
   a push that brushes a glass and still leaves the table better off is one the
   model can propose and the geometry cannot.
4. **Some toppled glasses, where the reference had none.** The reference's test
   push is a measurement; nothing this model says is.

And one prediction about the thing problem 4 adds, which is why
`--predicting` exists: **planning several pushes from one look should pay off
here and cannot pay off in problem 3.** A forward model can say where every
glass ends up, so the arm can push again without looking. In problem 3 seeing
was free, so there was nothing to buy.

## What it cost to train

Every number here is the arm's, not the laptop's, because in problem 4 that is
what a push costs.

| | tables | pushes | arm time | laptop time |
|---|---|---|---|---|
| Round 1, drawn at random | 1,200 | 5,404 | **9.4 hours** | 5 minutes |
| Round 1 again, on later tables | 1,200 | 5,367 | **9.5 hours** | 5 minutes |
| Round 2, the search's own | 300 | 1,482 | **2.4 hours** | 2 minutes |
| Validation, never trained on | 150 | 658 | 1.2 hours | 1 minute |
| Fitting three copies | | 12,253 pushes, 24,506 with their mirrors | — | 70 seconds |

**The second batch of random pushes is the plainest change this solution has
had, and it needed a second change to be worth anything.** It is drawn exactly
as the first was, on tables 2200 to 3399, so it cannot shift the mixture the
model is fitted on. On its own it improves the aim and spoils the refusal, for a
reason worth remembering: a model fitted on more pushes is less easily alarmed
about toppling, and the search's caution is a fixed threshold, so a less alarmed
model lets more marginal pushes through. The fit therefore now charges ten times
as much for a topple it fails to predict, which is `TOPPLE_SCALE` in
`train.py`, and [what changed](../../docs/04-clear-the-table/README.md)
has all four corners of that square.

A third round was collected and is **not** fitted on. It drew forty candidate
pushes at a time and made the one the three copies disagreed about most, and
those pushes really are the dangerous ones — 17.3% of them put a glass over,
against 10.4% drawn at random and 6.3% for the search's own picks. Fitted on
them the model separated the same tables and lost two and a half more glasses a
seed, so the round stays behind `collect.py --doubted` with its file named out of
the fit's reach, and `train.py --doubted` is how to repeat the measurement.

**Twenty-three arm hours for 12,911 pushes, where problem 3 collected 15,379 for
nothing.** That is the whole shape of the difference. A push there was one call
to a camera that saw the whole table; here the arm walks the ring of stands
before it knows where anything is, and walks to a stand again whenever the
glass it pushed is hidden from where it stands. A collecting table spends about
28 arm seconds and gives back four or five pushes.

Three things keep it to minutes of laptop time rather than hours.

- **A collecting table is pushed several times over.** The state after one push
  is the start of the next, so a table's build and its opening sweep are paid
  once for four or five examples. A glass going over ends it early, which is
  what holds the average down to four.
- **Collecting renders no pictures.** Which glasses a look catches is
  `wrist.in_picture`, which is geometry; the rendered frame beside it is for
  solutions that work from pixels, and this one does not. The glasses seen, the
  physics and the arm seconds charged are identical, and a test checks that by
  running one table both ways.
- **The reach is drawn over its whole range**, so more than half the pushes
  never touch the glass at all. Those are the cheap ones to simulate, and they
  are also the only thing in the set that can teach the model where contact is.

**On 658 validation pushes from tables nothing was trained on**, 254 really
moved a glass, by 35 mm at the median. The model puts those **13.3 mm from where
they land** at the median and 47 mm at the 90th; problem 3's puts its own 6.5
mm and 39 mm, on five times the data. At the 0.01 topple chance the search
works at, it catches **56 of the 70 pushes that really put a glass over**, and
flags 109 of the 588 that did not.

Both halves of the change above are visible in those four numbers, and the
clearest way to see it is together:

| 658 validation pushes | one round of random pushes | two rounds | two rounds, ten times the cost |
|---|---|---|---|
| where the glass lands, median | 5.7 mm | **4.3 mm** | 3.2 mm |
| where the glass lands, 90th | 38.3 mm | **31.7 mm** | 35.3 mm |
| when it really moved, median | 14.0 mm | **12.8 mm** | 13.3 mm |
| topples caught of 70 | 57 | 51 | **56** |
| safe pushes flagged of 588 | 116 | 94 | 109 |

The middle column is the trap: the best aim in the table and the worst refusal.
The right-hand column is the one the solution carries.

## What it does — twenty tables, seeds 0 to 19

The same twenty tables the geometry reference is calibrated on, and 84 glasses.
Both columns were measured on the current draw, after it was narrowed from four
to seven glasses down to three to five, and the reference's own
`calibration.json` is from before that and does not match what is here. Its
numbers below were taken again, with its own `calibrate.py`, and are in
`reference.json` beside this file; `make reference` writes it.

| | geometry reference | **this, the model** | this, `--predicting` |
|---|---|---|---|
| Tables separated | **5** of 20 | 4 of 20 | **5** of 20 |
| Tables failed by a topple | **0** | 5 | 4 |
| Glasses pickable at the end | **47** of 84 | 37 of 84 | 42 of 84 |
| Glasses broken | **0** of 84 | 5 of 84 | 4 of 84 |
| Arm seconds a table | 42.6 | **19.4** | 21.8 |
| Of which looking | 46% | 65% | 65% |
| It declared itself finished | 20 of 20 | 15 of 20 | 17 of 20 |
| …while the table was still crowded | 15 | **11** | 12 |
| Thinking an answer | 16 ms | **12 ms** | 14 ms |
| Pushes the cell's interlock refused | **0** | **0** | **0** |

**The one line to read is the second one.** Five of the twenty tables ended
with a glass on its side. A failed table pays nothing at all — every glass on
it leaves the pickable count while all of them stay in the total — so almost
the whole of the gap in the third row is those five tables and not a worse push
anywhere else.

That is not a guess. **On the fifteen tables this solution did not break a
glass on, it and the geometry reference are the same solution to within two
glasses, at half the arm time**: from the same 25 glasses pickable at the start,
it leaves 37 against the reference's 39, at 19.5 arm seconds a table against
42.3.

**These twenty tables are a small band and they disagree with the larger one.**
They are seeds 0 to 19, and the choice between this fit and the one before it
was made on a hundred and fifty tables walked under the real arm budget, where
this fit separates 15.7 tables a walk against 14.3 and loses 1.7 glasses against
3.0. On these twenty it loses five where the fit before it lost four. Twenty
tables is about a fifth of the sample and two glasses is inside the spread
between walks, so the twenty are reported and the hundred and fifty are what was
chosen on.

So the arm-time column is a real saving here, and it was not one before this
solution was changed. Three things pay for it: the ranging and test pushes are
gone, the search prefers the cheaper of two pushes it rates alike, and a
candidate whose hand would sweep a neighbour is thrown out rather than made and
looked at.

**What those five glasses were, measured rather than guessed.** Every push this
solution answers with is now recorded beside what the model believed about it,
which the page below asks for and nothing used to save. The five pushes that
put a glass over were given a chance of toppling something of **one in a hundred
thousand at the median**, and the worst of them one in three hundred, which is
still inside the limit the search works to — the model was not unsure, it was
wrong — and they were long: 48 mm at the median against 16 mm for the pushes
that broke nothing. That is the same finding as before the fit was changed, and
it is why tightening the limit was measured four times and never helped: **a
threshold cannot refuse what the model gives no chance at all.** A
long push is where this model is least reliable, and the price it pays for its
length is what decides how long its pushes are.

## Whether the predictions held

| | |
|---|---|
| **1. Fewer arm seconds a table.** | **Yes, and by half.** 19.4 against 42.6 over all twenty, and 19.5 against 42.3 on the fifteen it broke nothing on, so this is not an artefact of tables cut short. |
| **2. A higher share of the time spent looking.** | **Yes, 65% against 46%**, and the reason is that the pushes are shorter rather than that the looking is longer. |
| **3. More glasses made pickable.** | **No.** Two short of the reference on the tables it broke nothing on, and ten short over all twenty, which is the five it broke. |
| **4. Some toppled glasses, where the reference had none.** | **Yes.** 5 of 84, against 6 before the search was made pessimistic and 4 before the fit was given twice the pushes. This is still what costs it the comparison. |
| **5. Planning several pushes from one look pays off here.** | **No. It costs about a tenth more arm time for one table fewer.** |

**Why the looking share went up.** The reference's pushes are the *shortest*
that give a glass room — two to twenty millimetres, chosen by the geometry. The
model is free to choose any length up to a hundred, and before the search was
changed it chose long ones, because a longer push makes more room and nothing
weighed against it but a small price per millimetre. It now also pays for the
chance of a topple and has to find a corridor the hand can pass down, and both
of those prefer a shorter push: the pushes it makes are 19 mm at the median
where a push that broke a glass was 52 mm. So pushing costs less arm time than
it did, and the share spent looking rises without the looking changing.

**The price of a millimetre is still the knob that trades room against arm
time.** It was measured again after the search was changed, on a hundred tuning
tables with one search seed:

| what a longer push is made to cost | tables separated of 100 | glasses it gave room to | glasses over | arm seconds a table |
|---|---|---|---|---|
| **0.1 a millimetre (problem 3's, kept)** | **48** | **+136** | 3 | 25.7 |
| 0.3 a millimetre | 33 | +93 | 2 | 20.9 |
| 0.1, and no push longer than 60 mm | 39 | +120 | 2 | 25.2 |

Both ways of shortening the pushes lose nine to fifteen tables of a hundred to
save one glass, which is not a trade worth making: a table that is left crowded
is worth nothing either. The
same knob was measured on the search as it stood before — at 0.5 and above it
separated five to eleven tables of forty against fourteen to seventeen at 0.1 —
so the shape of the trade is the same and the pessimism has not changed it.
What the pessimism changed is the number of glasses broken at the price that
was already there, from 31 of 200 tuning tables to 9.

**Why believing the model is not cheaper than looking.** Three draws over forty
tuning tables, with and without a look between pushes:

| | arm seconds a table | tables separated of 40 | glasses pickable of 160 | answers |
|---|---|---|---|---|
| looking after each push | **29.5** | 15.3 | 100.7 | 1,055 |
| believing the model | 32.6 | 15.3 | 100.0 | 906 |

It answers 14% fewer times and spends 10% more arm time, for the same tables
and the same glasses. The reason is in the reference's own README: after a push
the jaw is standing right behind the glass facing it, so the look that judges
the push is usually **free** — another frame from a standing arm costs nothing
at all. What `--predicting` saves is a 1.5 second drive on the minority of
pushes where the glass ends up hidden. What it spends is extra pushes, made
from a belief that is 14 mm out at the median and 50 mm out at the tenth. In
problem 3 this trade could not even be stated, because seeing was free; in
problem 4 it can be stated, and the answer is no.

## Where it stands against the geometry, and what moved

In problem 3 this approach racked 146 glasses against the programmed
approach's 107, and the first measurement of this port did worse than the
geometry on every column but one. It now separates more tables than any other
solution to this problem. What follows is what changed and what did not.

**What changed is how the search treats its own model's estimates.** It reads
the least favourable of the three copies rather than their average, it pays for
a predicted chance of toppling rather than only obeying a limit on it, and it
throws out candidates whose hand would sweep a neighbour on the way in. None of
that was a better model: at the time the model was the same fitted file, the
same thirteen hours of arm time, the same 14 mm at the median. What changed is
that a search
which asks a model about a few thousand pushes and takes the best answer is
choosing the largest error, and three ways of not doing that are worth more here
than a better fit would have been.

**The data did change, one round later.** Doubling the random pushes — 12,253
against problem 3's 30,758, which is twenty-three arm hours against a camera
call — brought the landing error from 14 mm to 13.3 mm at the median and from
50 mm to 47 mm at the ninetieth, and it cost the refusal until the fit was made
to pay ten times as much for a missed topple. The section above has all four
corners of that; what matters here is that the search still rests on exactly
these predictions, and problem 3's model on five times the data is still twice
as accurate.

**What has never changed is what a mistake costs.** A table that loses a glass
pays nothing for any glass on it, by design, so that a risky shove can never be
profitable. That rule decided this solution's score when seven tables of a walk
were forfeited; it stopped deciding it when one was; and with five forfeited it
decides it again. The arithmetic further down puts the breakages at four to five
points of share, so they are once more the larger half of the gap to the
geometry, and tables reached and left crowded are the rest.

**The thing it is plainly better at is thinking**, and that is unchanged: 10 ms
an answer against the reference's 15, where problem 3's model thought four times
*longer* than its geometry. The reference's chooser walks 72 headings by 75 push
lengths in Python for every glass; the search asks three small networks about
800 pushes in one array and then checks a handful of corridors. Arm time is the
budget, so this buys nothing on the card — but it is the answer to "can a world
model be afforded here", and it is yes.

**The rung that was tried and dropped.** This page used to name the obvious next
step: keep the reference's five-millimetre test push in front of the model's long
pushes, so that the one thing the model is worst at is measured rather than
predicted. It was built and measured. On forty tuning tables it did cut the
glasses broken from four to one — and it cut the tables separated from seventeen
to **eight**, because a glass that does not keep up with a probe is then left
alone for the rest of the table. Once the search was pessimistic it bought
nothing that pessimism had not already bought, so it is not here.
[`what-changed.md`](../../docs/04-clear-the-table/README.md) holds the
numbers.

## What it scores — the held-out queue, fifty tables offered from 10,000

Everything above was measured on tables below `TEST_SEEDS`, which is where the
two settings were chosen and where nothing is a score. **This is the score.**
Fifty tables are offered in order from table 10,000, with fifteen arm minutes
for the **whole queue**, walked three times through the bench's own judging. The
geometry reference walked the same queue and is beside it. Medians of the three
walks, with the three values in brackets.

| | geometry reference | **this, the model** |
|---|---|---|
| Tables attempted | 26 | **39** (45, 38, 39) |
| Glasses on those tables | 102 | 155 (179, 151, 155) |
| Tables separated, nothing broken | 10 | **14** (14, 12, 15) |
| Tables failed by a topple | **0** | 5 (6, 5, 2) |
| Tables left unfinished | 16 | 22 (25, 21, 22) |
| Glasses pickable at the end | 64 | 92 (92, 83, 99) |
| Of those, had room already | 39 | 57 (59, 51, 57) |
| Glasses it gave room to | +25 | **+33** (+33, +32, +42) |
| Pickable share | **0.627** | 0.550 (0.514, 0.550, 0.639) |
| Glasses broken | **0** | 5 (6, 5, 2) |
| It said a table was finished | 24 of 26 | 36 of 39 (38, 32, 36) |
| …while the table was still crowded | 14 | 22 (24, 20, 22) |
| Tables the clock stopped | 2 | 1 (1, 1, 1) |
| Arm seconds for a table it separated | 43.6 | **25.3** (23.9, 25.3, 28.3) |
| Thinking an answer | 15 ms | **11 ms** |
| Pushes the cell's interlock refused | 0 | 0 |

**It still separates the most tables on this problem's card, and its share is
now below the geometry's by more than it was.** It separates fourteen tables
where the geometry separates ten, gives room to a third again as many glasses,
and reaches thirty-nine of the fifty tables in the same fifteen arm minutes
where the geometry reaches twenty-six — a table it separates costs it 25 arm
seconds against the geometry's 44. Against its own first walk of this queue:
eleven tables separated became fourteen and twenty-nine glasses freed became
thirty-three.

**The broken glasses are the row that moved the wrong way, and it is the one
honest difficulty of this round.** The fit before this one broke one glass a
walk here, and over six fresh walks it breaks one and a half; this one breaks
five. The choice between them was made on a hundred and fifty tables below the
held-out line, walked under the same arm budget, where this fit loses 1.7
glasses a walk against the other's 3.0 — so one band of forty tables disagrees
with three bands of fifty, in the opposite direction, and it disagrees over nine
different tables rather than one bad layout.
[What changed](../../docs/04-clear-the-table/README.md) says what was
checked before accepting that, and why the change is kept: the band below ten
thousand is where choosing happens, and reverting because the held-out tables
disagree is what the band exists to prevent.

**On the twenty-six tables the two share, it is ahead of the reference on both
columns of work done.** The card above compares two walks of different lengths,
which the comparison page's own
[prefix table](../results/README.md#the-same-tables-for-the-rows-that-reached-different-distances)
repairs by cutting every walk to the same tables. Cut to the reference's
twenty-six, this solution separates eleven tables against ten, frees
twenty-nine glasses against twenty-five, and breaks nothing on them. Its spread
there is eight to twelve separated tables, which holds the reference's ten, so
the fair statement is that it is level or a little ahead rather than clearly
ahead.

**Read the unfinished row beside the attempted row.** Twenty-five tables were
left crowded, against the geometry's sixteen, because it reached fourteen more
tables than the geometry did. The share is what makes those comparable, and it
is taken over every glass on every table attempted.

Both spend essentially the whole 900 seconds, so how far each got down the list
is set by what a table costs it. The rest of the fifty were offered and handed
straight back because what was left of the clock could not pay for the first
path; the bench does not count those, and the rule is in
[the examiner](../../docs/04-clear-the-table/README.md).

**The saving this port was made for is real.** A table it separates costs 25.4
arm seconds against the reference's 43.6, and that average is over tables that
were really finished, so a table cut short by a falling glass cannot flatter it.
The reach down the queue is where the saving went: thirty-nine tables against
twenty-six.

**The pickable share is below the geometry's, and the breakages are the larger
half of the reason again.** The arithmetic is the same each walk: take the share
as scored, then ask what it would have been had the forfeited tables merely been
left crowded, and then had they been separated.

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Pickable share, as scored | 0.514 | 0.550 | 0.639 |
| …had the broken tables merely been left crowded | 0.559 | 0.589 | 0.652 |
| …had they been separated instead | 0.654 | 0.682 | 0.684 |

The middle row is worth four and a half, three and nine tenths, and one and
three tenths points of share in the three walks, so **the breakages cost about
three points of the seven-point gap to the reference's 0.627**, and the tables
left crowded cost the rest. The third walk is the one to read against the other
two: it broke two glasses rather than six and scored 0.639, which is above the
reference. The fit before this one forfeited one table a walk and the middle row
was worth under two points; the walk-to-walk swing here is what five forfeited
tables does to a forty-table queue.

### Where the breakages are

Thirteen glasses went over in three walks: six in the first, five in the second
and two in the third, spread over nine different tables. Three of those tables
lose a glass in more than one walk — 10,011 and 10,022 twice each, and 10,035 in
all three — so about half the breakages are a handful of layouts this fit
handles badly, and the rest are spread.

That is a worse shape than the fit before it, which lost three glasses over
three walks on three different tables, and it is the measured cost of this
round's change to the fit. It is **not** the same shape as the first measurement
of this solution, where eight glasses went over and the tables from 10,018
onwards broke one in nearly every walk: there the breakages were a property of
one part of the queue, and here they are not.

**It is not the clock running low.** Nothing here reads `Look.seconds_left`, and
the budget still held minutes at each of them.

**And it is not what the band below ten thousand shows.** On a hundred and fifty
tables walked under the same budget, this fit loses 1.7 glasses a walk and the
one before it loses 3.0. That disagreement is the subject of
[what changed](../../docs/04-clear-the-table/README.md), which also
records the three things checked before it was accepted.

### What the per-push record now says

Every push this solution answers with is recorded beside what the model believed
about it — the chance it gave of toppling something, how far it pushed, and how
deep it reached. This page used to say that measurement was the thing that would
settle whether the model is wrong or the search trusts it too far, and that
nothing saved it. It is saved now, in `measurement.json` under `believed`.

On the twenty tuning tables, where five glasses went over: **the five pushes
that broke them were given a chance of one in a hundred thousand at the median,
and the worst of them one in three hundred**, which is inside the limit the
search works to; and they were long — 48 mm at the median against 16 mm for
every other push made. So the answer is not that the model was unsure and the
search pushed anyway. The model was confident and wrong, and it was confident
and wrong about exactly the longest pushes, which is where it has least data and
most to get wrong.

**That reading has now been acted on four times, and it is where this solution's
ceiling is.** The data was doubled, which improved the aim and did not stop the
long pushes going wrong. The limit on the predicted chance was tightened four
times, from one in a hundred down to three in ten thousand, and it never saved a
glass — because a threshold cannot refuse what the model gives no chance at all.
Testing a doubted glass with the reference's five-millimetre shove was built and
measured at three thresholds, and it cost up to four tables a walk while saving
nothing, because a short test says nothing about a long push in a cell where the
tipping rule can predict no glass at all. The fourth attempt is the section
below, which is the one that says why the first three could not have worked.

### What the topple head reads, and what the search asks it

The head's accuracy is reported on `validation.npz`, which is pushes drawn at
random. That is the wrong set to judge it on, and the right one costs one
command: `make collect-check` lets the search choose the pushes on 150 tables
nothing was fitted on, and `make check-planned` reads a fit on them. The set is
named outside the `train*.npz` glob, because a check set the model was fitted on
measures nothing.

| at a chance of 0.01 | topples caught | safe pushes flagged |
| --- | --- | --- |
| the kept fit, on random pushes | 56 of 70 | 109 of 588 |
| the kept fit, on the search's own pushes | **13 of 40** | 33 of 725 |
| fitted on a second planned round, on the same pushes | **22 of 40** | 51 of 725 |

**The head is good on the pushes it was trained on and poor on the pushes it is
asked about**, and the two sets differ because the search chose one of them. A
search that maximises over the model's own estimates picks the candidates the
model is confident and wrong about, so the head's false negatives *are* this
solution's broken glasses. That is the winner's curse stated in numbers, and it
is why no setting of the limit could ever have helped: the glasses go over on
pushes the head puts below any threshold worth having.

Two things follow, and the second is the one worth remembering. **The search is
already doing half the work of staying safe**, because its own pushes topple 5.2
per cent of the time against 10.4 per cent for random pushes. And **teaching the
head on exactly those pushes works on the head and not on the table.** A second
planned round of 300 tables, collected with this model rather than the one of
three weeks ago, takes the catch rate from 13 of 40 to 22 of 40 and the aim on
those pushes from 7.1 mm to 6.3 mm — and over nine clocked walks the solution
built on it separates 16.6 tables against 15.7, frees 45.0 glasses against 42.3,
and breaks 3.1 against 1.7. The caution limit was tried again at 0.003 and 0.001
on that better head, where it does now cut breakages for the first time, from
3.1 to 2.3, and never below the kept fit's 1.7. The price on risk was tried at
2.0 and 8.0 on both fits: 2.0 buys one glass and costs a hundredth and a half of
share, and 8.0 costs two separated tables. Eight configurations in all, and the
share runs from 0.604 to 0.640 with no ordering that survives the spreads.

**So the better model is not a better solution, and the round two fit is not
kept.** What a more capable model buys here is more work, and more work on this
table means more glasses on their sides. The remaining breakages are a limit of
what the camera can see — friction and the exact contact decide them — and not a
limit of the arithmetic in front of the model, which is why the next thing to
try is a different model of toppling rather than another setting.

### Which glass goes over, and what the model thought of the push

The sentence above names friction and the contact point as what decides a
breakage, and that claim can be checked, because two quite different faults end
a table the same way. If a glass *beside* the one being pushed goes over, the
clearance arithmetic let the hand pass too close and the repair belongs in the
arithmetic. If the glass *under the fingers* goes over, it tipped where it
should have slid, and the repair belongs in the model's account of toppling.
`measurement.json` cannot tell them apart, because the examiner ends the table
the moment a glass goes over and the look that would show which one is never
taken — so `make toppled` asks the bench instead, which is allowed in a
diagnosis because nothing in it decides a push.

| 300 tables from 5300 | glasses over |
| --- | --- |
| the glass being pushed went over | **30** |
| a glass not being pushed went over | **0** |

**Every breakage is the pushed glass, and not one is a neighbour.** The
clearance arithmetic is therefore doing its whole job: it is keeping the hand
away from glasses it is not aimed at, over three hundred tables, with no
exception. And the model's own belief about those thirty pushes was a chance of
2 in 10,000 at the median and 8 in 1,000 at the worst, against a limit of 1 in
100, so none of them was a push the search knew to be risky and took anyway.

That is the same winner's curse as the section above, now narrowed to one
sentence: **what is left to repair is a glass tipping instead of sliding under
fingers the model was confident about**, which is why the next thing to build is
a different account of toppling — a geometric one, resting on the contact height
against the glass's own measured foot, rather than a learned chance that the
camera has no way to see.

## Running it

```
make help               # every command, one line each
make collect            # round 1: 1,200 tables of random pushes, about 5 minutes
make collect-more       # round 1 again on later tables, about 5 minutes
make train              # about a minute
make collect-planned    # round 2: the search's own pushes on 300 new tables
make train              # again, on every round collected
make collect-check      # a planned round kept out of the fit, for reading the head
make check-planned      # read the fit on it: 13 of 40 topples caught, against 56 of 70 on random pushes
make toppled            # which glass went over on each table that lost one: 30 pushed, 0 neighbours
make select             # fifty tables below the held-out line, under the real clock
make measure            # the twenty tables above
make reference          # the geometry reference's own numbers, to sit beside
make test               # the checks; none of them needs a trained model
```

**`make select` is the one to choose on.** `make measure` gives every table as
much arm time as it wants, so it says whether a table *can* be separated; the
score gives fifteen arm minutes for fifty tables, so it says how much gets done
before the clock stops. Those are different questions, and two changes to this
solution were chosen on the first and lost on the second before the difference
was noticed. `make select` walks fifty tables from 500 under the real budget,
three times, which is the score's own shape on tables that may be chosen on.

`data/` and `weights/` are not in git, for the reason problem 3 keeps its own
out: they are made again by the two commands above.

The twenty tables are below `TEST_SEEDS` and are not the measurement.
`measure.py` refuses any seed from `TEST_SEEDS` up, and the held-out queue is
walked once, by the owner of the problem, through the bench's own judging:

```
pixi run python measure.py --judge      # writes results.json
```

The model is trained on tables 1000 to 2199, 2200 to 3399 and 4000 to 4299,
validated on 9000 to 9149, and its settings — the topple limit, the price of a
millimetre and what a missed topple costs the fit — were chosen on tables 500 to
749. None of those is one of the twenty, and none is held out. Tables 5000 to
5299 hold the third collecting round, which was measured and is not fitted on.
