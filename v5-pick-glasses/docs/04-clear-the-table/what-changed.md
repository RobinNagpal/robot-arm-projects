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

<!-- the remaining changes appear here as each is measured -->
