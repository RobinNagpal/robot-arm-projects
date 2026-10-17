# Problem 4 — geometry generates, a fitted model ranks

Plain geometry writes down every push that is legal. Problem 3's fitted model
puts the survivors in order, and the arm makes the first push on the list. The
model can never add a push and never bring back one the geometry refused, so a
wrong answer costs one wasted push and nothing worse.

This is [problem 3's solution
2](../../03-push-glasses-apart/02-geometry-ranked/) written to problem 4's
contract, and almost none of it is written here. The loop is [solution
1's](../01-one-fixed-nudge/) and the ranker is problem 3's own fitted file.
What is new is two choosers and a measurement.

## Why this solution is worth running at all

Solution 1 separates **5** of its twenty tables and leaves thirty-eight glasses
across them. Its own account of why is coarse. It cannot say whether a glass
had no legal push at all or had legal pushes that were every one of them too
slight to free it, because the printed rule throws its candidates away as it
goes, so both end up reported as nowhere clear to push the glass to.

A chooser that keeps every candidate can tell the two apart, and it is also the
reference most likely to find somewhere to push a glass that looks hemmed in.
So the question this solution answers is not "can a model beat a printed rule"
— problem 3 already measured that, and the answer was no. It is **how much of
what is left is the arrangement and how much is the choice.**

## What is borrowed and what is new

| | |
|---|---|
| `tour.py`, `remembered.py`, `jaw_paths.py`, `nudge.py` in solution 1 | **borrowed.** Where to stand to see the table, what has been seen, a push written out as waypoints, the ranging push, the test push, and the rule for saying done. |
| `candidates.py`, `features.py`, `ranker.py` in problem 3's solution 2 | **borrowed.** Every legal push as a set, the eight inputs, and the trees. |
| `model/ranker.joblib` in problem 3's solution 2 | **borrowed, loaded, not refitted.** |
| `borrowed.py` | **new.** The two folders above, loaded in one place. |
| `ranked.py` | **new.** The two choosers, and the subclass that plugs one into the loop. |
| `measure.py` | **new.** The numbers below, including the perfect-world run. |

`GeometryRanked` is `OneFixedNudge` with one method overridden. A test in this
folder checks that: every other method on the subclass has to be the same
object as the one on solution 1's class, so nothing can be copied here to
change a line in the middle of it.

**One line changed in solution 1's folder.** `nudge.py` called
`plan.choose(...)` in the middle of `_decide`; it now calls `self._choose(...)`,
which is a new method whose whole body is that same call. Nothing else moved,
and solution 1's 42 tests pass unchanged, as do the bench's.

**Loaded by file path, not by putting folders on the path.** Both folders this
is built from have names starting with a digit, so neither is a package.
`partners.py` reaches problem 3's solution 1 by putting its folder on
`sys.path`, and that is safe there because nothing needed from it shares a name
with anything else. It would not be safe here: problem 3's solution 2 would put
its own `candidates`, `run` and `test_ranked` beside this folder's files, and
which won would depend on where pytest was started. Problem 3's solution 2 had
the same problem reaching problem 3's solution 1 and solved it the same way, so
`borrowed.py` loads each file and registers it under the plain name its
siblings import it by.

## Could the ranker's inputs be computed here?

**Yes, all eight, and that was not obvious.** Problem 4 takes the overhead
camera away, so a look reaches only as far as the camera does, and the ranker
was fitted on a table handed over whole. Three of the eight inputs are about a
glass's neighbours — the contact angle relative to the nearest neighbour's
edge, the room the destination would have, and how many neighbours sit within
reach. Here they are computed over **the table as the arm believes it**, which
is every glass it has seen so far and no more.

Nothing fails and nothing had to be dropped. Two reasons:

- The inputs are *relations*, not addresses. Problem 3 chose them that way so
  that sliding the arrangement across the table changes nothing, and a relation
  computed over a subset of the table is still a number.
- The solution sweeps the whole ring of stands before it decides anything, so
  the belief it hands the ranker is usually the whole table. A sweep is 8 arm
  seconds and a table that pushes anything pays for two, so most of the 15
  seconds a table spends looking is this, and this is one of the things it
  buys.

A test computes all eight over subsets of each drawn table, down to a belief of
a single glass, and checks that every one comes out finite and that the trees
accept the row.

Two honest notes about the inputs rather than failures of them:

- **The belief can be wrong, and then the inputs are wrong.** A glass nobody
  has looked at yet is not in the count of neighbours, so a destination can be
  scored as roomy and turn out not to be. Solution 1's own chooser works from
  the same belief, so the two solutions are wrong in the same way and the
  comparison between them is still fair.
- **One input is no longer about the task.** "Destination to the rack" is still
  a distance this cell can compute, because the rack is part of the cell's
  layout, but problem 4 never racks a glass. It carried 0.05 of the fit's
  importance, so it is not doing much; it is left in place because dropping an
  input would mean refitting, and then a difference from problem 3 could be the
  fit rather than the problem.

## What it achieves — twenty tables, seeds 0 to 19

Measured on tables **below** `TEST_SEEDS`; the held-out tables are scored once
and not by a run read while a folder is being written. Solution 1's column is
its own `calibration.json`.

| | Ranked | Solution 1 |
|---|---|---|
| Glasses on them | 84, of which 33 already have room | the same tables |
| Tables separated with nothing broken | **4** of 20 | **5** of 20 |
| Glasses made pickable | 33 at the start, **43** at the end | 33, **47** |
| Glasses toppled | **0** of 84 | **0** of 84 |
| Arm time a table | **41.1 s** (44.9 s middling, 67.7 s worst) | 42.6 s (43.0, 74.5) |
| Of which looking | **44%** | 46% |
| Tables it declared finished | 20 of 20 | 20 of 20 |
| Paths the cell's interlock refused | 0 | 0 |
| The whole queue of 20 | 822 arm s | 852 arm s |
| Answers, and laptop time thinking | 706, 13.2 s | 744, 11.9 s |

**One table fewer and four glasses fewer, for 30 arm seconds less over the
queue.** The ranked chooser is the cheaper of the two here and the worse of the
two, and nothing was broken either way.

| why a glass was left | ranked | the same candidates, printed rule | solution 1 |
|---|---|---|---|
| tipped when tried | 24 | 22 | 22 |
| still without room after pushing | 15 | 14 | — |
| nowhere clear to push it to | 2 | 2 | 16 |
| tips before it slides | 1 | — | — |
| **total left** | **42** | **38** | **38** |

The middle column is the regrouping, and it is the reason to keep the
candidates. It leaves the same thirty-eight glasses solution 1 leaves, for the
same tables, because it is the same loop making the same pushes; all that
differs is what it can say about them. Solution 1 reports every glass it could
not place as "nowhere clear to push it to", because the printed rule throws its
candidates away as it goes. The candidate set keeps them, so sixteen glasses
become **2** that had no legal push at all and **14** whose legal pushes were
every one of them too slight to free the glass or to loosen the table. Only the
first two are really hemmed in.

The left-hand column is a different set of glasses, because the ranked chooser
made different pushes and ended the tables in different arrangements. The row
that barely moves across all three is the one that matters most: a little over
twenty glasses tipped when the test push tried them, whoever was choosing.

All three columns are a solution's own account rather than the scorer's.
Nothing marks a glass, so the reasons are read back out of the sentence a
solution gives when it says it is finished, and that sentence is written from
what the arm believes. Each column therefore counts one glass more than the
scorer finds without room — 42 against 41 for the ranked chooser, 38 against 37
for the other two — which is measurement error of about the right size.

## The ordering changes the destination, and for the worse

The ablation run takes the identical loop over the identical candidate set and
lets problem 3's printed rule pick instead of the trees. That isolates the
sort: nothing else differs.

| | Ranked | Printed rule, same candidates |
|---|---|---|
| Tables separated | 4 | **5** |
| Glasses pickable at the end | 43 | **47** |
| Arm time a table | **41.1 s** | 42.6 s |
| Answers | **706** | 744 |
| Thinking | 13.2 s | **12.6 s** |

The right-hand column reproduces solution 1's own calibration run number for
number — 42.58 arm seconds a table, 43.03 middling, 74.48 worst, 744 answers,
724 paths followed, the same five tables separated — which is the check that
this folder enumerates exactly what solution 1 chooses from. A test asserts the
two pick the same push. The only figure that differs is the laptop thinking
time, 12.6 seconds against solution 1's 11.9, because this folder enumerates
the whole candidate set before picking the push solution 1 picks first.

**The model disagrees constantly, and on this draw the disagreement costs
something.** Over the 128 decisions where any candidate existed, the ranker's
pick was one the printed rule would have been equally happy with **13 times**,
and a push the rule ranks below it **115 times**. The twenty tables end one
separated table and four freed glasses worse than the printed rule left them.

(The comparison is made on the rule's own measure and not by comparing the two
pushes, because the rule takes the *first* shortest freeing push and so can name
a different push of exactly the same length when the set is handed to it in a
different order. Counting that as a disagreement would make the number depend on
the sort it is there to measure.)
This is worse than the finding problem 3 reported. There the ranker reached the
same result as the printed rule and paid more arm time for it — "beaten on the
cost of a result it matches" — so the sort was a waste and not a loss. Here it
does not match the result: it separates one table fewer and frees four glasses
fewer, and it does so for slightly *less* arm time. The sort has stopped being
free.

The reason is in the fit, and problem 3 already named it. The two inputs that
carry four fifths of the importance are **push height over the topple limit**
(0.43) and **foot width** (0.38): the model mostly learned which glass is risky
to push, not which push is good. That is a useful thing to know and it is not a
thing that frees a glass.

### The obvious repair, measured and not kept

The trees are fitted on the room a push gains and are never shown what the push
costs to make, so the obvious reading is that they prefer the longest push and
that pricing a millimetre of push would fix the ordering. **Measured, it does
nothing.** Four prices were tried on forty tuning tables, from nothing to three
times the price problem 3's world model pays for the same trade:

| what a millimetre of push costs the candidate asking for it | tables separated of 40 | glasses it gave room to | glasses broken |
|---|---|---|---|
| nothing, as the trees are used | 15 | +40 | **0** |
| 0.05 | 15 | +40 | **0** |
| 0.1, the world model's price | 14 | +39 | **0** |
| 0.3 | 15 | +39 | **0** |

Nothing moves, at any price, and the arm time a table moves by less than a tenth
of a second. So the ordering's fault is not that its pushes are too long: it is
that the thing the trees are good at predicting — whether a push would tip a
glass — is not the thing a chooser needs to know, because the candidate set the
geometry hands them has already thrown out the pushes that would tip anything.
The knob is not in the solution, and `ranked.py` carries this measurement so that
the next person to have the idea finds it answered.

## Whether these tables can be separated at all

This is the measurement the solution exists for. `measure.py --perfect` takes
the arm away: true positions, every push landing exactly where it aimed, no
clock, and as many pushes as the chooser wants. A glass the geometry says tips
before it slides is still refused, because that refusal belongs to the chooser.

| twenty perfect tables | Ranked | Printed rule |
|---|---|---|
| Tables separated | **11** of 20 | **12** of 20 |
| Glasses with room at the end | 66 of 84 | 67 of 84 |
| Pushes it found to make | 40 | 30 |
| Left with only pushes too slight to help | 16 | 15 |
| Left with no legal push at all | 1 | 2 |
| Left as tippy before it would slide | 1 | — |

**The answer is yes, and most of what a real run loses is the arm.** Eleven or
twelve of the twenty tables come apart when nothing goes wrong, and the
choosers run out of pushes worth suggesting after thirty or forty of them
across the whole twenty. The real runs reach four and five. So of the fifteen
or sixteen tables that end crowded with a real arm, seven or eight were
winnable and were not won, and the explanation is not the arrangement.

It is not the chooser either, because the two columns above are within one
table of each other and the real runs are within one table of each other. What
is left is seeing and pushing a real glass, and the foot is where that goes
wrong. Solution 1's README measures it directly: a glass slides rather than
tips only while half its foot over the friction is more than the 107 mm the
jaw's top edge stands at, the cell's own table friction is 0.35, and 49 of the
51 crowded glasses on these twenty tables have a foot narrower than the 75 mm
that demands. Every one of the twenty tables holds at least one such glass.

**The perfect world has no friction in it, and that is exactly why its ceiling
is higher.** It asks the same tipping rule the solutions ask, and that rule
works from the plausible range of friction, 0.2 to 0.5, rather than from the
cell's real value. The range lets it say "no" only to a foot narrower than
43 mm, so it refuses almost nothing and the perfect run then moves the glass.
One glass in the ranked column was refused that way, and it is a glass that
started its table with room, which is the one case the draw does not check: the
draw redraws a *crowded* glass until the rule stops saying "no" to it, and a
glass that only became crowded after a push was never held to that.

**So the geometry reference is the better of the two here, and neither of them
is the ceiling.** Twelve of twenty is what a later solution has to aim at, and
the room between twelve and five is in the physics of a push rather than in the
arrangement. Getting at it means doing something neither of these does: pick a
glass up, push it lower down than the jaw's top edge, push two at once, or
settle the tipping question some way other than shoving the glass and watching.

**An earlier draw answered no, and that is why it is gone.** This section used
to report none of twenty tables separated in the perfect world, after
thirty-one pushes across the whole twenty, and it concluded from that the
geometry reference was the ceiling and this solution was the proof of it. That
was true of the draw it was measured on, which asked for four to seven glasses
with a touching pair **and** a touching group of three on every table. A draw
whose ceiling is zero ranks nothing, since every solution scores zero on it for
the same reason, so it was replaced by the draw measured here — three to five
glasses with one touching group — and the conclusion went with it.

## How wide the choice really is

Worth recording, because a ranking over one candidate is the printed rule
wearing a hat.

| | |
|---|---|
| Decisions over the twenty tables | 165 |
| Candidates offered | 20,706, **126 a decision** |
| The widest single group | 792 |

So the ranker was given real choices and used them, on 115 of the 128
decisions where any candidate existed, and the tables came out a table worse.
The size of the groups is why the thinking time is higher: the enumeration is
nearly all of it, and this solution enumerates the same pushes solution 1
enumerates and then scores them as well.

## What it achieves — the held-out queue

Everything above chose numbers; this is the score. The examiner offers fifty
tables in order from table 10,000, gives **fifteen arm minutes for the whole
queue**, and lets each table spend as much of what is left as it needs. The
queue is walked three times. Solution 1's column is its own held-out run on the
same queue with the same budget.

| | Ranked | Solution 1 |
|---|---|---|
| Tables attempted | **25** of fifty | 26 of fifty |
| Glasses on them | 98 | 102 |
| Tables separated with nothing broken | **7** | **10** |
| Tables failed by a topple | 0 | 0 |
| Tables left unfinished | 18 | 16 |
| Glasses broken | 0 | 0 |
| Glasses pickable | 38 at the start, **57** at the end | 39, **64** |
| Glasses freed | **19** | **25** |
| Pickable share at the end | 0.582 | 0.627 |
| It said it was finished | on 24 tables; the clock stopped 1 | on 24; the clock stopped 2 |
| Said finished while still crowded | 17 | 14 |
| Paths the interlock refused | 0 | 0 |
| Arm time spent | 899.23 s of 900 | 899.98 s of 900 |
| Arm time for a table it separated | 41.7 s | 43.6 s |
| Answers, and thinking an answer | 796, 15 ms | 813, 15 ms |

**Nothing varies between the three walks, for either solution.** Every count is
identical, and so is every per-table row: the same outcome, the same arm
seconds to the hundredth, the same number of answers. There is no spread to
quote, and writing one as "± 0" would offer a measured zero where the true
statement is that neither solution has anything to vary. Given a table, each
always answers the same way. This one enumerates the candidate pushes in a
fixed order, scores each with trees that are loaded from a file and never
refitted, and takes the first on the sorted list; nothing is sampled anywhere.
A fitted model is not the same thing as a random one. The repeats exist for the
solutions that come later, which draw their action from a distribution rather
than computing it and whose training carries a random seed of its own, so the
same method trained twice is two policies of different quality. The examiner
asks everybody for three walks, and these two answer the same thing three
times. The only figure that moves at all is the laptop thinking time, about
0.2 s of spread over 12 s a walk, which measures the machine and not the
method.

**The band above and this one are not the same tables, but they are the same
draw.** The twenty tables earlier on this page are drawn below the held-out
line and these fifty from table 10,000 up, and both bands are three to five
glasses with one touching group. Every measured number on this page, the
perfect-world run included, was taken after the first draw was replaced, and
the sections above say what that first draw was and why a ceiling of zero made
it useless for ranking anything. So the two bands tell one story: the tables
are separable, and this solution finishes behind solution 1 in both of them —
four tables against five above, seven against ten here.

### The ranked chooser loses, and the rows say where

It has strictly more machinery than solution 1 for the same task — every legal
push instead of the first one the printed rule names — and it finishes behind
on both counts that matter: seven tables separated against ten, and nineteen
glasses freed against twenty-five. That is the result. The per-table rows say
where the six glasses went.

**It is not the shorter queue.** Both solutions spend essentially the whole
budget, so the length of the queue is set by what a table costs them, and this
one reaches twenty-five tables where solution 1 reaches twenty-six. But the
twenty-sixth table bought solution 1 almost nothing: it was stopped by the
clock after 2.3 s and three answers, and freed no glass on it. Of the six
glasses between the two solutions, exactly **one** is owed to the shorter
queue, and it is on the table before that one — solution 1 reached table 10,024
with 38.5 s of budget left and freed a glass there, while this solution reached
it with 4.6 s left, spent 3.8 of them, and freed none. **No separated table
is owed to the queue at all.**

**It is not the clock, the interlock, or a topple.** Both numbers are zero
everywhere, and all five of the tables the two solutions disagree about ended
with the solution saying it was finished, not with the clock stopping it.

**It is five tables out of twenty-five.** Both solutions reached tables 10,000
to 10,024, and both declared themselves finished on exactly the same
twenty-four of them. On twenty of the twenty-five the outcome is the same, and
five of those twenty cost each solution a single sweep and nothing else,
because neither chooser found anything it would push. The whole difference sits
in five tables, and this solution wins one of them.

| table | solution 1 | ranked | |
|---|---|---|---|
| 10,006 | crowded, 1 glass freed, 63.3 s, 56 answers | **separated**, 2 freed, 45.5 s, 41 answers | ranked wins |
| 10,008 | **separated**, 2 freed, 43.5 s, 41 answers | crowded, 0 freed, 38.0 s, 35 answers | |
| 10,014 | **separated**, 3 freed, 94.3 s, 71 answers | crowded, 1 freed, 94.1 s, 74 answers | |
| 10,015 | **separated**, 3 freed, 60.8 s, 53 answers | crowded, 2 freed, 54.1 s, 47 answers | |
| 10,017 | **separated**, 2 freed, 46.3 s, 41 answers | crowded, 1 freed, 51.4 s, 44 answers | |

Eleven glasses against six on those five tables, plus the one glass on table
10,024, is the six. On the twenty-five tables both reached, the pickable share
is 0.643 for solution 1 against 0.582 for this one.

**"Said done while crowded" is the same fact counted again, not a second
symptom.** Both solutions declared themselves finished on twenty-four tables,
and a declared table is either separated or crowded, so twenty-four is ten and
fourteen for solution 1 and seven and seventeen for this one. The three extra
crowded finishes **are** the three lost tables. Both solutions use the same
stopping rule — it is solution 1's code, borrowed whole — so nothing about
saying "done" differs between them. What differs is the arrangement the rule is
asked about.

**It does not simply give up earlier, either.** On two of the four tables it
loses it stops sooner than solution 1 does, and on the other two it works
longer and achieves less: on table 10,014 it makes three more answers for the
same arm time and frees two fewer glasses, and on table 10,017 it spends five
seconds more and frees one fewer. So "it quits early" does not cover the
result.

**The extra arm time is real but it is not where the tables went.** On the
twenty-four tables both solutions walked to their own finish, this one spends
895.4 arm seconds against solution 1's 861.5 — 33.9 s more, four per
cent. Most of it is on tables it does separate: over the six tables both of
them separate it spends 246.1 s against 190.8 s, twenty-nine per cent more,
with 209 answers against 177. That extra third of a minute is exactly what
costs it the twenty-sixth table and the one glass on table 10,024. It is not
what costs it three separated tables.

**Its lower arm time for a separated table is an artefact of which tables it
won, not evidence that it is quicker.** The average is taken over successful
tables only, so the expensive tables this solution lost drop out of it: table
10,014 cost 94 s and counts in solution 1's average as a success and in this
one's not at all, although this solution spent the same 94 s there. On the
tables both of them separate, this solution is the slower of the two by
twenty-nine per cent.

### Why ordering by the model costs tables

The tuning band measures the ordering directly, because the ablation there runs
the same loop over the same candidates with the printed rule picking. Over the
128 decisions where any candidate existed, the model picked a push the printed
rule ranks below its own on **115** of them, and the twenty tables ended one
separated table and four freed glasses worse than the printed rule left them.
The held-out queue is the same result over a longer queue, three tables rather
than one. The first draw of problem 4 hid this: the model
disagreed just as constantly there and cost nothing at all, because on a set of
tables where no ordering can win any ordering is as good as any other. This
draw has something to spoil, and a worse order spoils it.

**What the model learned is which glass is risky, not which push helps.** The
two inputs carrying four fifths of the fitted importance are the push height
over the topple limit, at 0.43, and the width of the glass's foot, at 0.38.
Both are about whether the glass would go over, and neither is about whether
the push leaves the glass with room. Sorting by that is harmless when nothing
can be won and harmful when something can, and it fits the shape of the losses:
nothing was toppled, nothing was refused by the interlock, and the glasses were
simply left where the pushes put them.

**Where the rows run out, and the one measurement that would settle it.** The
held-out rows hold a table's outcome, its arm seconds, its answers and how many
glasses had room before and after. They do not hold which push was chosen, for
which glass, whether the glass gained room by it, how many of its four allowed
tries it had spent, or the reason each glass was finally left alone. Three
readings fit what is recorded, and they are not exclusive:

- the ranked pick is legal but too small to free its glass, so a glass spends
  its four tries and the loop leaves it alone — table 10,014, where more
  answers in the same time freed fewer glasses, has that shape;
- the ranked pick sends a glass somewhere clear on the believed table but into
  a third glass's room, so the table never settles — the extra time on the
  tables both solutions separate has that shape;
- the ranked order frees the easy glasses first and leaves the hard one
  surrounded, with nowhere for the hand to come in.

**None of them can be told apart from these rows, so none is asserted here.**
What would settle it is a per-decision log of the five tables above: for every
answer, the glass, the push, whether that glass gained room, and the reason
each glass was finally left, set beside solution 1's log of the same table.
That is five tables of the held-out queue and no new machinery — the
tuning-band run already records the reasons a glass was left, and the held-out
rows merely do not keep them.

## Running it

```
make help
make measure     # the twenty tables above, about 35 seconds; writes measurement.json
make rule        # the same loop and candidates with the model deleted
make perfect     # the arm taken away; writes perfect.json
make test        # the quick checks, about 10 seconds
make lint
```

Or from `04-clear-the-table` directly:

```
pixi run python 02-geometry-ranked/measure.py --tables 20
pixi run pytest -q 02-geometry-ranked
pixi run ruff check 02-geometry-ranked
```

`measure.py` refuses any seed from `TEST_SEEDS` up.

**It needs problem 3's fitted file**, at
`../../03-push-glasses-apart/02-geometry-ranked/model/ranker.joblib`. That file
is not in git — problem 3 regenerates it with `make train` in its own folder,
which spends about five minutes making pushes and under two seconds fitting the
trees. `load_ranker` says so in those words if it is missing, rather than
failing on a pickle. Nothing here fits anything, which is the point: the only
difference between problem 3's solution 2 and this one is the problem.

`scikit-learn` is in problem 4's environment for that one file. The trees were
fitted under problem 3's version and load under problem 4's without complaint.

## Three things this port found

**The candidate set reproduces the printed rule exactly, and that is the test
worth having.** The ablation matches solution 1's own calibration run on every
arm second, every answer and all 724 paths the bench followed. Two enumerators
that agree on a push are easy to write and hard to be sure of; two runs that
agree on 724 paths are the same enumerator.

**No feature needed dropping, because problem 3 chose relations over
addresses.** The inputs were designed so that moving the arrangement would not
change them, and the same property is what lets them be computed over the part
of the table the arm has looked at. A feature set with x and y in it would have
been fine in problem 3 and useless here.

**"Still without room after pushing" is a better refusal than "nowhere clear to
push it to", and it costs nothing to say.** Solution 1 cannot tell the two
apart because its chooser discards the candidates it rejected. This one keeps
them, and over the same twenty tables solution 1's sixteen glasses with
"nowhere clear to push it to" turn out to be 2 with no legal push at all and 14
whose every legal push was too small to matter. So the commonest of those two
reasons is not that the table is full. That is a different problem from a full
table, and it points at a different fix.
