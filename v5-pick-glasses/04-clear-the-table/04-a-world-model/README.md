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
  the arm's reach;
- the model predicts a movement longer than the push itself, which is the model
  answering outside what it has seen.

The rest are scored by how much room the table would still be short of
afterwards, plus a small price per millimetre pushed. The best push over all
the glasses is made, unless the cell's own interlock would refuse it — that is
checked before the push is answered, because a refused path moves the arm
nowhere, so the solution would be shown the same table back and would spend
that glass's four tries proposing the same push. Then the arm looks again and
the search runs afresh.

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
| Tables separated | **5** of 20 | 4 of 20 | **5** of 20 |
| Tables failed by a topple | **0** | 6 | 6 |
| Glasses pickable at the end | **47** of 84 | 34 of 84 | 39 of 84 |
| Glasses broken | **0** of 84 | 6 of 84 | 6 of 84 |
| Arm seconds a table | 42.6 | **34.1** | 35.7 |
| Of which looking | 46% | 36% | 51% |
| It declared itself finished | 20 of 20 | 14 of 20 | 14 of 20 |
| …while the table was still crowded | 15 | **10** | **9** |
| Thinking an answer | 16 ms | **7 ms** | 8 ms |
| Pushes the cell's interlock refused | **0** | 3 | 1 |

**The one line to read is the second one.** Six of the twenty tables ended with
a glass on its side. A failed table pays nothing at all — every glass on it
leaves the pickable count while all of them stay in the total — so almost the
whole of the gap in the third row is those six tables and not a worse push
anywhere else.

That is not a guess. **On the fourteen tables this solution did not break a
glass on, it and the geometry reference are the same solution to the glass and
to the second**: 23 glasses pickable at the start and 34 at the end, either
way; four tables separated, either way; 39.3 arm seconds a table against 39.5.
On the six it broke, the reference separated one of them and made three more
glasses pickable.

So the arm-time column is not the saving it looks like. Most of it is tables
that ended early because a glass went over, and a table that stops after one
push is a cheap table.

## Whether the predictions held

| | |
|---|---|
| **1. Fewer arm seconds a table.** | **No, not really.** 34.1 against 42.6 over all twenty, but 39.3 against 39.5 on the fourteen it finished. The difference is six tables cut short by a falling glass. |
| **2. A higher share of the time spent looking.** | **No — lower, 36% against 46%**, and the reason is interesting. |
| **3. More glasses made pickable.** | **No.** Identical on the tables both finished, and 13 fewer over all twenty. |
| **4. Some toppled glasses, where the reference had none.** | **Yes.** 6 of 84. This is the only one that held, and it is the one that cost the rest. |
| **5. Planning several pushes from one look pays off here.** | **No. It costs about a tenth more arm time for the same result.** |

**Why the looking share went down rather than up.** The reference's pushes are
the *shortest* that give a glass room — two to twenty millimetres, chosen by
the geometry. The model is free to choose any length up to a hundred, and it
does, because a longer push makes more room and the price of a millimetre is
set low. A push crosses the table at 20 mm a second, so a hundred-millimetre
push is five arm seconds. Measured over all twenty: looking fell from 326 to
298 seconds, and pushing rose from 380 to 530. Taking the ranging and test
pushes out did buy the looking back — there is no longer a glass to go and
re-measure after every five-millimetre poke — and the search spent it on longer
pushes.

**The price of a millimetre is therefore the knob that trades room against arm
time, and it is the one number this port should have had to change.** Measured
on forty tuning tables, two draws each:

| price of a millimetre pushed | tables separated of 40 | glasses pickable of 160 | glasses over | arm seconds a table | looking |
|---|---|---|---|---|---|
| **0.1 (problem 3's, kept)** | 14, 17 | 98, 106 | 6, 4 | 29.7, 30.5 | 48% |
| 0.5 | 10, 11 | 85, 90 | 1, 3 | 26.9, 26.3 | 58% |
| 1.0 | 5, 5 | 75, 76 | 1, 1 | 17.1, 20.0 | 71% |
| 2.0 | 1, 1 | 67, 66 | 0, 0 | 11.8, 11.3 | 86% |

A shorter push is a cheaper push and a safer one, and it separates far fewer
tables. The budget belongs to a queue of fifty tables, so the arithmetic that
settles it is tables per budget times separations per table: at 30 arm seconds
a table the 900-second budget reaches 30 tables and separates about 11 of them;
at 19 seconds it reaches 48 and separates about 6. So problem 3's figure stays,
now because it was measured rather than because it was inherited.

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

## Why it does not beat the geometry here, when it did in problem 3

In problem 3 this approach racked 146 glasses against the programmed
approach's 107. Three things are different here, and they all point the same
way.

**The model is fitted on a fifth of the data, because the data costs arm time.**
6,886 pushes against 30,758. It lands a glass 14 mm from where it said against
problem 3's 6.5 mm, and the search's cost is built out of exactly those
predictions.

**A mistake costs more.** In problem 3 a toppled glass ended that table and the
glasses already racked stayed racked. Here a table that loses a glass pays
nothing for any glass on it, by design, so that a risky shove can never be
profitable. Six topples in twenty tables is therefore six tables scoring zero
rather than six tables scoring less.

**The headroom it won in problem 3 is not there.** Its edge came from not being
bound by the reference's rule that the hand's corridor must be clear of every
neighbour, which let it find pushes the geometry refused. On this draw the
geometry is not often short of pushes — it separates 5 of these 20 tables and
14 of 40 tuning tables — and what decides a table is whether a crowded glass
can be pushed at the jaw's height at all. Both solutions meet the same physics
there. The reference settles it by poking the glass five millimetres and
looking, which is a *measurement*; the model settles it with an estimate that
is right 57 times in 70.

**The one thing it is plainly better at is thinking.** 7 ms an answer against
the reference's 16, where problem 3's model thought four times *longer* than
its geometry. The reference's chooser walks 72 headings by 75 push lengths in
Python for every glass; the search asks three small networks about 800 pushes
in one array. Arm time is the budget, so this buys nothing — but it is the
answer to "can a world model be afforded here", and it is yes.

**The obvious next rung** is not a better model. It is to keep the reference's
five-millimetre test push in front of the model's long pushes, so that the one
thing the model is worst at is measured rather than predicted, and let the
model choose everything else. That is a different solution from this one, and
it should be built as one.

## What it scores — the held-out queue, fifty tables offered from 10,000

Everything above was measured on tables below `TEST_SEEDS`, which is where the
two settings were chosen and where nothing is a score. **This is the score.**
Fifty tables are offered in order from table 10,000, with fifteen arm minutes
for the **whole queue**, walked three times through the bench's own judging. The
geometry reference walked the same queue and is beside it. Medians of the three
walks, with the three values in brackets.

| | geometry reference | **this, the model** |
|---|---|---|
| Tables attempted | 26 | **32** (32, 33, 32) |
| Glasses on those tables | 102 | 125 (125, 130, 125) |
| Tables separated, nothing broken | 10 | **11** (12, 8, 11) |
| Tables failed by a topple | **0** | 7 (5, 8, 7) |
| Tables left unfinished | 16 | 15 (15, 17, 14) |
| Glasses pickable at the end | 64 | 70 (70, 64, 71) |
| Of those, had room already | 39 | 39 (41, 39, 38) |
| Glasses it gave room to | +25 | **+29** (+29, +25, +33) |
| Pickable share | **0.627** | 0.560 (0.560, 0.492, 0.568) |
| Glasses broken | **0** | 8 (6, 8, 8) |
| It said a table was finished | 24 of 26 | 24 of 32 (25, 24, 24) |
| …while the table was still crowded | 14 | 13 (13, 16, 13) |
| Tables the clock stopped | 2 | 1 (2, 1, 1) |
| Arm seconds for a table it separated | 43.6 | **26.7** (26.9, 24.1, 26.7) |
| Thinking an answer | 15 ms | **6 ms** |
| Pushes the cell's interlock refused | 0 | 0 |

Both spend essentially the whole 900 seconds, so how far each got down the list
is set by what a table costs it. The rest of the fifty were offered and handed
straight back because what was left of the clock could not pay for the first
path; the bench does not count those, and the rule is in
[the examiner](../../docs/04-clear-the-table/the-examiner.md).

**The saving this port was made for is real, and the twenty tables could not
show it.** A table it separates costs 26.7 arm seconds against the reference's
43.6. That average is over tables that were actually finished, so a table cut
short by a falling glass cannot flatter it — which is exactly the objection that
made prediction 1 read "no, not really" above. On the eighteen tables where it
breaks nothing at all it spends 498 to 557 seconds against the reference's 698.
The reach down the queue is where that saving went: 32 tables against 26.

**And it is level with the geometry on separations rather than ahead of it.**
Eleven against ten, but the three walks gave 12, 8 and 11 while the reference is
deterministic and gives 10 every time. A method that wins by less than its own
spread has not been shown to win. What it is ahead on is glasses given room:
+29 against +25, over six more tables.

**The pickable share is below both geometry solutions', and the whole of the
difference is the breakages.** Of the 125 glasses it met, 19, 30 and 27 stood on
tables it broke a glass on, and such a table pays nothing for any glass on it.

| | walk 1 | walk 2 | walk 3 |
|---|---|---|---|
| Pickable share, as scored | 0.560 | 0.492 | 0.568 |
| …had those tables merely been left crowded | 0.616 | 0.577 | 0.648 |
| …had those tables been separated instead | 0.664 | 0.662 | 0.720 |

The middle row is what doing *nothing at all* on those seven tables would have
scored, and it is the whole of the gap to the reference's 0.627.

### Where the breakages are, which is one place

| tables | walks | separated | failed | glasses given room | glasses broken |
|---|---|---|---|---|---|
| 10,000–10,017 | 54 | 9, 6, 7 of 18 | **0** | +22, +19, +22 | **0 of 68** |
| 10,018–10,025 | 24 | 2, 2, 2 of 8 | 3, 3, 4 | +8, +6, +8 | 4, 3, 4 of 34 |
| 10,026 on | 19 | 1, 0, 2 | 2, 5, 3 | +2, +1, +5 | 2, 5, 4 |

**All twenty breakages across all three walks are on table 10,018 or later, and
the first eighteen tables were attempted fifty-four times without one.** That is
not the clock running low: nothing here reads `Look.seconds_left`, and the
budget still held over five minutes at the first breakage. It is those tables,
and the reference proves it independently — deterministic, same list, and on
10,018 to 10,025 it separates **none** and gives room to **one** glass, saying
the table was finished on six of the eight. On two of them it sweeps, finds no
push it is willing to make, and says so in 8 seconds.

Lined up table by table over the 26 tables both reached:

- it breaks a glass on five of them, and the reference separates **none** of
  those five;
- it separates five the reference never separates, all of them tables the
  reference leaves crowded;
- it never separates three that the reference does;
- there is **no table where the reference succeeds and this breaks a glass.**

So the wins and the breakages come out of the same decision — being willing to
push where the geometry finds no clear corridor. Two of those eight hard tables
it wins in every walk; three or four end on the floor. Table 10,023 is the
clearest: the reference sweeps it and declines in 8 seconds, and this loses a
glass on it in two walks of three.

### What the rows settle about why, and what they do not

**The cell never refused a push**, in any walk. The interlock is pre-checked
here, so every broken glass came from a push both the model and the public
tipping rule called acceptable; nothing in the cell was placed to save it.

**It is not a stale belief.** Nine of the twenty breakages are the ninth answer
of the table — the eight stands of the opening sweep, then one push. That is the
freshest and most complete belief this solution ever holds. Seventeen of twenty
are inside the first twenty answers.

**The rows point at the search rather than at the model, without settling it.**
On validation the filter at 0.01 passes 472 of the 588 safe pushes and 13 of the
70 that toppled, so about three in a hundred passed pushes put a glass over.
A table takes a handful of pushes, so that rate predicts a breakage on well
under a tenth of tables; the hard stretch breaks about half of them. Pushes the
search *chose* are therefore several times more dangerous than pushes the same
filter passed when they were drawn at random, which is what maximising over a
model's own estimates does. The competing reading — that the hard tables simply
have no safe push, so any filter leaks on them — fits the rows equally well.

**What would settle it** is a per-push record: for every push answered, the
predicted topple chance, the predicted movements, and what really happened,
grouped by whether the reference would have pushed on that table. It costs no
arm time. Nothing saves it today, and `results-tables.json` has only the
outcome of a table, not the push that ended it.

**The price of a millimetre was chosen honestly and still cost it.** On the forty
tuning tables the inherited 0.1 was better by both readings — more tables
separated *and* a higher pickable share, 0.61 to 0.66 against 0.53 to 0.56 at
0.5. The queue returned 0.560 for the same setting, because the queue reaches
past where the tuning band went, into tables where the same willingness buys
fewer separations and more floor.

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
