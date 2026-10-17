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
[`what-changed.md`](../../docs/04-clear-the-table/what-changed.md) measures what
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
| Round 2, the search's own | 300 | 1,482 | **2.4 hours** | 2 minutes |
| Validation, never trained on | 150 | 658 | 1.2 hours | 1 minute |
| Fitting three copies | | 6,886 pushes, 13,772 with their mirrors | — | 40 seconds |

**Thirteen arm hours for 7,544 pushes, where problem 3 collected 15,379 for
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
moved a glass, by 35 mm at the median. The model puts those **14 mm from where
they land** at the median and 50 mm at the 90th; problem 3's puts its own 6.5
mm and 39 mm, on five times the data. At the 0.01 topple chance the search
works at, it catches **57 of the 70 pushes that really put a glass over**, and
flags 116 of the 588 that did not.

## What it does — twenty tables, seeds 0 to 19

The same twenty tables the geometry reference is calibrated on, and 84 glasses.
Both columns were measured on the current draw, after it was narrowed from four
to seven glasses down to three to five, and the reference's own
`calibration.json` is from before that and does not match what is here. Its
numbers below were taken again, with its own `calibrate.py`, and are in
`reference.json` beside this file; `make reference` writes it.

| | geometry reference | **this, the model** | this, `--predicting` |
|---|---|---|---|
| Tables separated | **5** of 20 | 4 of 20 | 3 of 20 |
| Tables failed by a topple | **0** | 4 | 4 |
| Glasses pickable at the end | **47** of 84 | 40 of 84 | 39 of 84 |
| Glasses broken | **0** of 84 | 4 of 84 | 4 of 84 |
| Arm seconds a table | 42.6 | **18.9** | 20.9 |
| Of which looking | 46% | 63% | 62% |
| It declared itself finished | 20 of 20 | 16 of 20 | 16 of 20 |
| …while the table was still crowded | 15 | **12** | 13 |
| Thinking an answer | 16 ms | **13 ms** | 17 ms |
| Pushes the cell's interlock refused | **0** | **0** | **0** |

**The one line to read is the second one.** Four of the twenty tables ended
with a glass on its side. A failed table pays nothing at all — every glass on
it leaves the pickable count while all of them stay in the total — so almost
the whole of the gap in the third row is those four tables and not a worse push
anywhere else.

That is not a guess. **On the sixteen tables this solution did not break a
glass on, it and the geometry reference are the same solution to within one
glass, at half the arm time**: 27 glasses pickable at the start, 40 at the end
against the reference's 41, four tables separated against five, and 19.7 arm
seconds a table against 42.8.

So the arm-time column is a real saving here, and it was not one before this
solution was changed. Three things pay for it: the ranging and test pushes are
gone, the search prefers the cheaper of two pushes it rates alike, and a
candidate whose hand would sweep a neighbour is thrown out rather than made and
looked at.

**What those four glasses were, measured rather than guessed.** Every push this
solution answers with is now recorded beside what the model believed about it,
which the page below asks for and nothing used to save. The four pushes that
put a glass over were given a chance of toppling something of **one in ten
thousand or less** — the model was not unsure, it was wrong — and they were
long: 52 mm at the median against 19 mm for the pushes that broke nothing. A
long push is where this model is least reliable, and the price it pays for its
length is what decides how long its pushes are.

## Whether the predictions held

| | |
|---|---|
| **1. Fewer arm seconds a table.** | **Yes, and by half.** 18.9 against 42.6 over all twenty, and 19.7 against 42.8 on the sixteen it finished, so this is not an artefact of tables cut short. |
| **2. A higher share of the time spent looking.** | **Yes, 63% against 46%**, and the reason is that the pushes are shorter rather than that the looking is longer. |
| **3. More glasses made pickable.** | **No.** One short of the reference on the tables it finished, and seven short over all twenty, which is the four it broke. |
| **4. Some toppled glasses, where the reference had none.** | **Yes.** 4 of 84, down from 6 before the search was made pessimistic. This is still what costs it the comparison. |
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
that is a better model: the model is the same fitted file, the same thirteen
hours of arm time, the same 14 mm at the median. What changed is that a search
which asks a model about a few thousand pushes and takes the best answer is
choosing the largest error, and three ways of not doing that are worth more here
than a better fit would have been.

**What did not change is the data.** The model is still fitted on a fifth of
problem 3's pushes, because in problem 4 the data costs arm time: 6,886 pushes
against 30,758. It lands a glass 14 mm from where it said against problem 3's
6.5 mm, and everything the search builds rests on exactly those predictions.

**What also did not change is what a mistake costs.** A table that loses a
glass pays nothing for any glass on it, by design, so that a risky shove can
never be profitable. That rule used to decide this solution's score, when seven
tables of a walk were forfeited. With one table forfeited it no longer does: the
arithmetic further down shows the breakages are now worth about two points of
share, and what is left of the gap to the geometry is tables reached and left
crowded.

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
[`what-changed.md`](../../docs/04-clear-the-table/what-changed.md) holds the
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
| Tables attempted | 26 | **40** (40, 40, 41) |
| Glasses on those tables | 102 | 160 (160, 160, 164) |
| Tables separated, nothing broken | 10 | **14** (11, 14, 15) |
| Tables failed by a topple | **0** | 1 (0, 1, 2) |
| Tables left unfinished | 16 | 25 (29, 25, 24) |
| Glasses pickable at the end | 64 | 98 (94, 100, 98) |
| Of those, had room already | 39 | 59 (61, 59, 59) |
| Glasses it gave room to | +25 | **+39** (+33, +41, +39) |
| Pickable share | **0.627** | 0.598 (0.588, 0.625, 0.598) |
| Glasses broken | **0** | 1 (0, 1, 2) |
| It said a table was finished | 24 of 26 | 39 of 40 (39, 39, 37) |
| …while the table was still crowded | 14 | 25 (28, 25, 22) |
| Tables the clock stopped | 2 | 1 (1, 0, 2) |
| Arm seconds for a table it separated | 43.6 | **25.4** (24.0, 25.4, 28.5) |
| Thinking an answer | 15 ms | **10 ms** |
| Pushes the cell's interlock refused | 0 | 0 |

**This is the best row on this problem's card.** It separates fourteen tables
where the geometry separates ten, gives room to half again as many glasses, and
reaches forty of the fifty tables in the same fifteen arm minutes where the
geometry reaches twenty-six — a table it separates costs it 25 arm seconds
against the geometry's 44. Against its own first walk of this queue, which is
what [`what-changed.md`](../../docs/04-clear-the-table/what-changed.md) records:
eleven tables separated became fourteen, eight broken glasses became one, and
twenty-nine glasses freed became thirty-nine.

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
[the examiner](../../docs/04-clear-the-table/the-examiner.md).

**The saving this port was made for is real.** A table it separates costs 25.4
arm seconds against the reference's 43.6, and that average is over tables that
were really finished, so a table cut short by a falling glass cannot flatter it.
The reach down the queue is where the saving went: forty tables against
twenty-six.

**The pickable share is a little below the geometry's, and the breakages are no
longer the reason.** This is the clearest single change. The share that doing
nothing at all on the broken tables would have scored is now within two points
of the share it really got, and in the walk that broke nothing the two are the
same number:

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Pickable share, as scored | 0.588 | 0.625 | 0.598 |
| …had the broken tables merely been left crowded | 0.588 | 0.638 | 0.616 |
| …had they been separated instead | 0.588 | 0.656 | 0.646 |

Before the search was changed the middle row was the whole of the gap to the
reference's 0.627, because seven tables of thirty-two were forfeited. Now one
table is, and what is left of the gap is tables left crowded rather than tables
lost — which is the ordinary business of not having separated them yet.

### Where the breakages are, which is now almost nowhere

Three glasses went over in three walks of forty tables: table 10,023 in one
walk, and tables 10,027 and 10,035 in another. The third walk broke nothing at
all. **No table breaks a glass in more than one walk**, and the first eighteen
tables were attempted fifty-four times without a single breakage.

That is a different shape from the first measurement of this solution, where
eight glasses went over and the tables from 10,018 onwards broke one in nearly
every walk. The band those tables fall in is walked clean now, so the
breakages are no longer a property of a part of the queue. They are what is
left of the risk the search still accepts, spread thinly.

**It is not the clock running low.** Nothing here reads `Look.seconds_left`, and
the budget still held several minutes at each of those three breakages.

### What the per-push record now says

Every push this solution answers with is recorded beside what the model believed
about it — the chance it gave of toppling something, how far it pushed, and how
deep it reached. This page used to say that measurement was the thing that would
settle whether the model is wrong or the search trusts it too far, and that
nothing saved it. It is saved now, in `measurement.json` under `believed`.

On the twenty tuning tables, where four glasses went over: **the four pushes
that broke them were given a chance of one in ten thousand or less**, and they
were long — 52 mm at the median against 19 mm for every other push made. So the
answer is not that the model was unsure and the search pushed anyway. The model
was confident and wrong, and it was confident and wrong about exactly the
longest pushes, which is where it has least data and most to get wrong.

That points at the one knob this solution still has: the price of a millimetre
pushed. Raising it does shorten the pushes, and measured on a hundred tuning
tables it loses fifteen separated tables to save one glass, which is why it
stays where it is. **The next rung is therefore the data rather than the
search**: pushes longer than about fifty millimetres are where the model is
weakest, and they are a small part of what it was fitted on.

## Running it

```
make help               # every command, one line each
make collect            # round 1: 1,200 tables of random pushes, about 5 minutes
make train              # about a minute
make collect-planned    # round 2: the search's own pushes on 300 new tables
make train              # again, on both rounds
make measure            # the twenty tables above
make reference          # the geometry reference's own numbers, to sit beside
make test               # the checks; none of them needs a trained model
```

`data/` and `weights/` are not in git, for the reason problem 3 keeps its own
out: they are made again by the two commands above.

The twenty tables are below `TEST_SEEDS` and are not the measurement.
`measure.py` refuses any seed from `TEST_SEEDS` up, and the held-out queue is
walked once, by the owner of the problem, through the bench's own judging:

```
pixi run python measure.py --judge      # writes results.json
```

The model is trained on tables 1000 to 2199 and 4000 to 4299, validated on
9000 to 9149, and its two settings — the topple limit and the price of a
millimetre — were chosen on tables 500 to 539. None of those is one of the
twenty, and none is held out.
