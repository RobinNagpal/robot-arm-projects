# Problem 4 — the programmed way, with no view of the whole table

Problem 4's task is problem 3's: some glasses stand too close together for the
gripper to get round them, and the arm pushes them apart. Two things are taken
away. The camera above the table is gone — the arm carries its own — and
nothing hands a push over one at a time, so the solution runs until it says it
is finished.

This is the geometry reference for it: no training, no model, nothing learned.
It is [problem 3's solution 1](../../03-push-glasses-apart/01-one-fixed-nudge/)
with the part that chooses a push **imported rather than copied**, and the parts
the overhead camera used to make unnecessary written here.

## What is borrowed and what is new

| | |
|---|---|
| `plan.py` in problem 3's solution 1 | **borrowed, unchanged.** The tipping rule, the 5 mm test push, the search for a safe push, the choice between pushes. `import plan` in this folder means *that* file. |
| `tour.py` | **new.** Where to stand to see the table. |
| `remembered.py` | **new.** What has been seen, merged across looks. |
| `jaw_paths.py` | **new.** A push written out as the jaw's own waypoints, which is what problem 4's contract takes. |
| `nudge.py` | **new.** The loop: sweep, decide, push, sweep again, say done. |

Nothing in this folder is called `plan.py` or `run.py`, and that is not a
preference. `partners.py` puts problem 3's solution 1 on the import path, and
that folder has the same name as this one, so a file here with either of those
names would shadow the file it is meant to be borrowing from — and which one
won would depend on where pytest was started.

## The loop

**1. Sweep.** Walk the ring of stands and look from each one. A stand is a pose
the jaw can hold at travel height, off the rim of the glass zone, facing across
it. There are eight of them on this cell, one for each bearing the arm can
reach, and walking all eight costs about 8 seconds of arm time.

The tour is every side rather than the fewest sides, and the reason is
occlusion. One of the eight poses already frames the whole glass zone, so a
tour chosen to cover the *ground* would be one stand — and it would miss
glasses, because a glass standing behind a nearer one is not in the picture
however well framed the table under it is. Which glass hides which depends on
where the glasses are, which no tour worked out from the cell alone can know.
Looking from every side is the general cure: two glasses in line from one
bearing are not in line from another. Measured over the same twenty tables as
below, the eight stands between them catch all 117 glasses on all twenty. The
best stand on a table catches nine glasses in ten and an average one seven in
ten, so the sweep is buying the last glass rather than the first — and the last
glass is the one that would otherwise be declared finished unseen.

**2. Remember.** Each look is folded into one picture of the table. Readings of
the same glass are averaged, because every look draws its own error and the
looks are nearly free. A glass that has just been pushed is forgotten first, so
that a reading taken after the shove is not averaged with readings of where it
used to be.

Merging goes by the glass numbers the bench hands back. Deciding that the glass
in this picture is the one from the last picture is the **association problem**,
and it belongs to problem 2. Nothing here solves it.

**3. Decide.** Problem 3's chooser, on the remembered table. Glasses that
already have room are held back from it: problem 3 racks a glass the moment it
has room, so its chooser never sees one, and nothing is racked here.

**4. Find the glass, test it, then push.** This is where problem 4 changes the
most, and the change is not optional.

Problem 3 puts the fingertips down 10 mm outside the glass's *widest* part and
then **creeps forward until its force sensor finds the glass**, pushing only
from there — 30 mm of `FEEL_BEYOND` is the allowance for it, and the allowance
is needed, because the jaw meets a glass at the jaw's own height, where the
glass can be far narrower than at its widest. Measured against the cell: the
fingertips travel 10 to 11 mm to meet a straight glass, 11 to 18 a tapered or
short-stemmed one, and **19 to 30 mm to meet a stemmed one**, where what they
meet is the stem.

A chunk cannot creep. So the distance has to be *measured*, and the only sense
problem 4 leaves for measuring it is the camera: push a little, look, and see
how far the glass went. That makes the test push two pushes.

- **Ranging.** Drive the fingertips 5 mm deeper than last time and look. This
  says nothing about whether the glass slides — only whether it has been met.
- **Testing.** Now that the distance is known, make problem 3's experiment
  exactly: push the glass 5 mm and look.
- **Pushing.** Every push of that glass from then on is written from the
  measured distance, so it lands the glass where the planner aimed instead of
  short of it.

Two of problem 3's own numbers do new work here, and both are explained where
they are used in `nudge.py`. The test asks whether the glass **kept up** with
the fingertips rather than whether it budged, because the ranging push has
already taken up the slack problem 3's threshold allows for. And how deep the
ranging may go is bounded by problem 3's own lean guard — `PROBE_LEAN_SHARE` of
the angle the glass would fall past — because a camera cannot tell "not touched
yet" from "touched, and leaning", and reaching deeper on that reading is how
you put a glass on its side.

**5. Look again, from one side.** A push is carried out open-loop, so the glass
has to be measured again — from the stand it should be least hidden from, worked
out from what is believed about the rest of the table. One stand, not the ring:
the ring is what it costs to make a claim about the whole table, and no claim is
being made yet.

**6. Say done.** When the chooser has nothing left worth pushing, walk the whole
ring once more and ask again. Only then is the table declared finished. Running
out of arm time is never reported as "done": that ending belongs to the clock,
and a solution that called it "done" would be claiming it knew when to stop.

## How it differs from problem 3's solution 1

| | problem 3's solution 1 | this |
|---|---|---|
| Seeing | one call, the whole table, free | eight poses, 8 arm seconds a sweep |
| Across looks | nothing to carry; each look is the table | a merged belief, averaged, and forgotten per glass when it moves |
| An action | a `Push`, expanded by the bench | a `Chunk` of waypoints, written here |
| Feeling for the glass | creep forward until the force sensor finds it, then push | no force sensor and no creeping: the distance to the glass is measured with the camera, by a ranging push, and remembered |
| Glasses with room | racked, and gone from the table | left standing, and held back from the chooser |
| Budget | 4 pushes a glass, 16 a table, counted by the bench | arm seconds, and a guard of 4 pushes a glass so one glass cannot absorb a table |
| Ending | the table is empty or every glass is refused | the solution says so, after a sweep |

## What it costs — twenty tables, seeds 0 to 19

These are the numbers `open_run.ARM_BUDGET` is to be set from. They are measured
on tables **below** `TEST_SEEDS`; the held-out tables are scored once and not by
a calibration run.

| | |
|---|---|
| Arm time a table | **31.1 s** on average, 28.4 s in the middle, 72.0 s at worst |
| Of which looking | **56%** |
| The whole queue of 20 | 621 arm seconds |
| Answers | 568 over 20 tables, and 13.7 seconds of laptop time thinking in total |

The looking splits three ways. A sweep of the ring is 8 seconds, and a table has
one at the start and, if anything was pushed, one before it is declared
finished. The look after a push is usually free, because the jaw ends up
standing behind the glass facing it and another frame from a standing arm costs
nothing; when the glass is not in that picture, the arm drives to a side it
should not be hidden from, about 1.5 seconds. On the five tables where the
chooser found nothing safe to do at all, the whole table is one sweep: 8
seconds, and done.

## What it achieves — the same twenty tables

| | |
|---|---|
| Tables separated with nothing broken | **0** of 20 |
| Glasses broken | **0** of 117 |
| Glasses pickable | 30 at the start, **33** at the end |
| Tables it declared finished | 20 of 20 |
| Paths the cell's interlock refused | 0 |

| why a glass was left | glasses |
|---|---|
| nowhere clear to push it to | 67 |
| tipped when tried | 16 |
| tips before it slides | 2 |
| lost sight of it after pushing | 1 |

**Zero tables separated is the draw and not the solution, and that is worth
being precise about.** Two measurements say so.

Take the physics away and the answer does not change. Give the chooser the true
positions, let every push land exactly where it aimed, and let it push as often
as it likes: it separates **0 of these 20 tables**, and 7 of 20 of problem 3's.
One fixed nudge cannot undo a touching group of three, which every problem 4
table holds and no problem 3 table has to.

Take the geometry away and the answer still does not change. A glass slides only
while half its foot over the friction is more than the jaw's top edge, so at the
cell's own friction of 0.35 it needs a foot wider than **75 mm**. Of the 89
crowded glasses on these twenty tables, **85 have a narrower foot than that**,
and **all 20 tables hold at least one**. They do not tip because the push was
clumsy; they tip because they are too narrow in the foot to be pushed at 107 mm
up by anything. The one honest way to clear them is to refuse them, which is
what happens.

So the first group in the table above is the hand's width — free space on the
table, but nothing a 139 mm hand can reach into — and the second and third are
its height. Nothing broke, which is the test push and the lean bound doing their
job.

## What it achieves — the held-out queue

The two sections above chose this solution's own numbers, and this one is its
score. The examiner offers fifty tables in order from table 10,000, gives
**fifteen arm minutes for the whole queue**, and lets each table spend as much
of what is left as it needs. The queue is walked three times.

| | |
|---|---|
| Tables attempted | **26** of the fifty offered |
| Glasses on them | 102 |
| Tables separated with nothing broken | **10** |
| Tables failed by a topple | **0** |
| Tables left unfinished | 16 |
| Glasses broken | **0** |
| Glasses pickable | 39 at the start, **64** at the end, a gain of 25 |
| Pickable share at the end | **0.627** |
| It said it was finished | on 24 tables; the clock stopped the other 2 |
| Said it was finished while the table was still crowded | 14 |
| Paths the cell's interlock refused | 0 |
| Arm time spent | 899.98 s of the 900 given |
| Arm time for a table it separated | **43.6 s** |
| Answers | 813, at 15 ms of laptop thinking each |

**Nothing varies between the three walks.** Not one count above differs, and
the per-table rows are identical table for table: the same outcome, the same
arm seconds to the hundredth, the same number of answers. So there is no spread
to quote, and quoting one as "± 0" would suggest a measured zero where the
right statement is that this solution has nothing to vary. Given a table it
always answers the same way, because every step of it is arithmetic: the push
is computed from the measurements, the ranging and test pushes are fixed
lengths, the ring of stands is walked in a fixed order, and no number anywhere
is drawn. The only figure with any movement in it is the laptop thinking time,
0.2 s of spread over about 12 s a walk, and that measures the machine rather
than the method. The three walks are therefore a check that the measurement
reproduces, not a sample of a distribution. A trained solution needs the
repeats for a real reason — it draws its action rather than computing it, and
its training has a random seed of its own — so the examiner asks everybody for
three walks and this solution simply answers the same thing three times.

**The two bands are not the same tables.** The twenty tuning tables above were
measured before the draw was simplified: a table then held four to seven
glasses with a touching group of three on every one of them, and nothing could
separate such a table at all, which is why that section reports none of twenty
separated. A table now holds three to five glasses with one touching group,
which is a pair on about half of them. So the tuning numbers still show what
the numbers above were chosen on, and the arm times in them are still the right
order of magnitude, but **the zero in them is not a result about these
tables**. The held-out queue settles that question directly: ten of twenty-six
tables are separated, so the tables are separable and the method separates
them.

**Two tables in three are reached, and the twenty-sixth was worth nothing.**
The queue is fifty tables long on purpose, so a solution runs out of time
rather than out of tables, and this one stops at the twenty-sixth. It arrived
there with 38.5 s of the budget left, spent 36.2 s on table 10,024 and 2.3 s on
table 10,025 before the clock caught it, and freed one glass between the two.
Five of the twenty-six tables cost only one sweep of the ring each — about 8 s
and nine answers — because the chooser found nothing safe to push and the
solution said so after a second sweep.

**Fourteen tables were declared finished while still crowded, and that is the
honest shape of the method.** It is not a claim that the table was clear: the
loop says it is finished when the chooser has no push left that it is willing
to make, and it sweeps the whole ring once more before saying it, so what the
fourteen record is glasses the geometry would not touch rather than glasses it
failed to notice. The other side of the same caution is the zero in the broken
column and the zero interlock refusals: over 813 answers the cell never once
had to refuse a path for driving into a glass that would tip.

**Against the ranked chooser.** [Solution 2](../02-geometry-ranked/) walks the
same queue with every legal push enumerated and a fitted model sorting them,
and it separates seven tables where this one separates ten. The two agree on
twenty of the twenty-five tables they both reached, and its own README works
through the five they disagree on.

## Running it

Problem 4's own environment may not be installed yet. Either way:

```
# from 04-clear-the-table, once its environment exists
pixi run python 01-one-fixed-nudge/calibrate.py --tables 20
pixi run pytest -q 01-one-fixed-nudge

# until then, from 03-push-glasses-apart, whose environment has everything
pixi run pytest -q ../04-clear-the-table/01-one-fixed-nudge
pixi run ruff check ../04-clear-the-table/01-one-fixed-nudge
```

`calibrate.py --save calibration.json` writes the numbers above. It refuses any
seed from `TEST_SEEDS` up.

`conftest.py` is what makes the second form work: pytest adds the folder a test
sits in and not the bench beside it, and `pixi run` replaces `PYTHONPATH` rather
than adding to it, so a path set on the command line never reaches Python.

## Three things about problem 4 this solution found

**Nothing is charged for crossing the table between actions — except that
`clock.py` now charges it separately.** The cell puts the jaw above a path's
first waypoint without simulating the trip. If that were free, a look from the
far corner would cost what a look from where the jaw stands costs, and the trade
this problem exists to measure would vanish. `clock.crossing_seconds` is what
closes it, so a path here starts at the point it is about to work at and the
trip to it is the clock's business.

**Another frame from a standing arm is free, and that is correct.** A path of one
waypoint, at the pose the jaw is already in, moves nothing and costs nothing.
The 5 mm test push needs three looks either side of it to beat the measurement
error down, and in problem 4 those are free where in problem 3 they were simply
not counted. Moving to see costs arm time; seeing again does not.

**A camera cannot tell "not touched yet" from "touched, and leaning".** The
glass does not move either way, and the force sensor is what told problem 3
apart. Every resolution of that ambiguity costs something: resolving it by
reaching deeper topples leaning glasses, and resolving it by refusing leaves
every glass that is narrow at the jaw's height standing where it was. This
solution reaches deeper, but only as far as problem 3's own lean guard allows,
and refuses after that. It is the safe way to be wrong, and it is the same
direction problem 3 is wrong in.
