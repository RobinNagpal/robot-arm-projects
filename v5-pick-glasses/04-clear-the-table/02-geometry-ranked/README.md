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

Solution 1 separates **none** of its twenty tables, and it is not the loop that
fails. Give its chooser the true positions, let every push land exactly where
it aimed, and let it push as often as it likes, and it still separates none: one
fixed nudge cannot undo a touching group of three, and every problem 4 table
holds one. Sixty-seven of the eighty-six glasses it leaves are left because
there was nowhere clear to push the glass to.

A chooser that considers every candidate instead of taking the first is the
reference most likely to find somewhere. So the question this solution answers
is not "can a model beat a printed rule" — problem 3 already measured that, and
the answer was no. It is **whether these tables can be separated at all.**

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
  seconds and a table that pushes anything pays for two, so most of the 18
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
| Tables separated with nothing broken | **0** of 20 | **0** of 20 |
| Glasses made pickable | 30 at the start, **33** at the end | 30, **33** |
| Glasses toppled | **0** of 117 | **0** of 117 |
| Arm time a table | **32.4 s** (31.1 s middling, 81.6 s worst) | 31.1 s (28.4, 72.0) |
| Of which looking | **55%** | 56% |
| Tables it declared finished | 20 of 20 | 20 of 20 |
| Paths the cell's interlock refused | 0 | 0 |
| The whole queue of 20 | 649 arm s | 621 arm s |
| Answers, and laptop time thinking | 582, 15.4 s | 568, 13.7 s |

**The same end, for 4% more arm time.** Same tables, same glasses, same
breakages, 28 arm seconds more over the queue.

| why a glass was left | ranked | solution 1 |
|---|---|---|
| still without room after pushing | 59 | — |
| nowhere clear to push it to | 8 | 67 |
| tipped when tried | 16 | 16 |
| tips before it slides | 2 | 2 |
| lost sight of it after pushing | 1 | 1 |
| **total left** | **86** | **86** |

The first two rows are the same glasses grouped differently, and the regrouping
is worth having. Solution 1 reports every glass it could not place as "nowhere
clear to push it to", because `plan.choose` throws its candidates away as it
goes. The candidate set keeps them, so this solution can say which glasses had
**no** legal push at all — 8 of them — and which had legal pushes that were all
too slight to free the glass or to loosen the table — 59. Only the first group
is really hemmed in. The other three rows are identical glasses for identical
reasons.

## The ordering changes the route and not the destination

`measure.py --rule` runs the identical loop over the identical candidate set
with problem 3's printed rule picking instead of the trees. That isolates the
sort: nothing else differs.

| | Ranked | Printed rule, same candidates |
|---|---|---|
| Tables separated | 0 | 0 |
| Glasses pickable at the end | 33 | 33 |
| Arm time a table | 32.4 s | **31.1 s** |
| Answers | 582 | **568** |
| Thinking | 15.4 s | **13.7 s** |

The right-hand column reproduces solution 1's `calibration.json` number for
number — 31.07 arm seconds a table, 28.35 middling, 71.96 worst, 568 answers,
548 paths followed — which is the check that this folder enumerates exactly
what solution 1 chooses from. A test asserts the two pick the same push.

**The model disagrees constantly and it changes nothing.** Over the 85
decisions where any candidate existed, the ranker's pick was one the printed
rule would have been equally happy with **15 times**, and a push the rule ranks
below it **70 times**. The twenty tables still end in the same arrangement.

(The comparison is made on the rule's own measure and not by comparing the two
pushes, because the rule takes the *first* shortest freeing push and so can name
a different push of exactly the same length when the set is handed to it in a
different order. Counting that as a disagreement would make the number depend on
the sort it is there to measure. It happens on about one decision in thirty.) This is the same finding problem 3 reported — "where it
used to be beaten on the result, it is now beaten on the cost of a result it
matches" — reproduced on a harder problem, and it is slightly sharper here,
because problem 3's ranker at least reached the same fourteen tables by a
different route while here there is no route to anywhere.

The reason is in the fit, and problem 3 already named it. The two inputs that
carry four fifths of the importance are **push height over the topple limit**
(0.43) and **foot width** (0.38): the model mostly learned which glass is risky
to push, not which push is good. That is a useful thing to know and it is not a
thing that frees a glass.

## Whether these tables can be separated at all

This is the measurement the solution exists for. `measure.py --perfect` takes
the arm away: true positions, every push landing exactly where it aimed, no
clock, and as many pushes as the chooser wants. A glass the geometry says tips
before it slides is still refused, because that refusal belongs to the chooser.

| twenty perfect tables | Ranked | Printed rule |
|---|---|---|
| Tables separated | **0** of 20 | **0** of 20 |
| Glasses with room at the end | 42 of 117 | 45 of 117 |
| Pushes it found to make | 31 | 26 |
| Left with no legal push at all | 10 | 10 |
| Left with only pushes too slight to help | 65 | 62 |

**The answer is no, and the chooser is not what is in the way.** Twenty tables,
a chooser looking at every candidate, nothing going wrong, and it runs out of
pushes to suggest after **31 pushes across all twenty tables** — one or two a
table. It is not choosing badly; there is nothing left to choose.

That matters because it closes off a whole family of explanations for solution
1's zero. The zero is not the loop, not the camera on the arm, not the ranging
push, not the measurement error and not the ordering. It is the draw against
this hand: a Robotiq 2F-85 is 139 mm across and cannot push below 75 mm, so on
these tables most crowded glasses are too narrow in the foot to be pushed at
all, and the ones that can be pushed have nowhere to go that is 139 mm clear of
everything else. Solution 1's README measures that directly — 85 of 89 crowded
glasses have a foot narrower than the 75 mm the cell's friction demands, and all
twenty tables hold at least one.

**So the geometry reference is the ceiling here, and this solution is the proof
rather than an improvement on it.** Any later solution that separates a problem
4 table will have to do something neither of these does: pick a glass up, or
push two at once, or move a glass through a gap neither chooser will aim at
because the hand does not fit.

## How wide the choice really is

Worth recording, because a ranking over one candidate is the printed rule
wearing a hat.

| | |
|---|---|
| Decisions over the twenty tables | 122 |
| Candidates offered | 9,611, **79 a decision** |
| The widest single group | 398 |

So the ranker was given real choices and used them (70 disagreements), and the
tables came out the same. The size of the groups is why the thinking time is
higher: the enumeration is nearly all of it, and this solution enumerates the
same pushes solution 1 enumerates and then scores them as well.

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
worth having.** `--rule` matches solution 1's `calibration.json` on every
number, including the 548 paths the bench followed. Two enumerators that agree
on a push are easy to write and hard to be sure of; two runs that agree on 548
paths are the same enumerator.

**No feature needed dropping, because problem 3 chose relations over
addresses.** The inputs were designed so that moving the arrangement would not
change them, and the same property is what lets them be computed over the part
of the table the arm has looked at. A feature set with x and y in it would have
been fine in problem 3 and useless here.

**"Still without room after pushing" is a better refusal than "nowhere clear to
push it to", and it costs nothing to say.** Solution 1 cannot tell the two
apart because its chooser discards the candidates it rejected. This one keeps
them, and the breakdown turns out to be 8 against 59 — so the commonest reason
a glass is left is not that the table is full, but that every push the geometry
will allow is too small to matter. That is a different problem, and it points
at a different fix.
