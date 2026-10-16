# Solution 2 — geometry generates, a model ranks

> **What it uses** — the same arithmetic as [solution
> 1](01-one-fixed-nudge.md), plus one fitted model: a small ensemble of
> decision trees, trained in problem 3 and loaded here without being trained
> again.
> **What it does** — Plain geometry writes down every push that is legal on the
> table as the arm believes it. The model scores each one and puts them in
> order. The arm makes the first push on the list. Everything else — walking
> the ring of stands to see the table, merging the looks, finding the glass
> before pushing it, and deciding that the table needs nothing more — is
> solution 1's, borrowed whole.
> **What it costs** — Nothing to train, because the trees were fitted in
> problem 3 and are reused. Nothing to rent, because scoring a list of pushes
> is a few thousand sums. It costs about four per cent more arm time than
> solution 1 across the tables it works on.
> **The cell is described once, in [the cell](../../the-cell.md)**, and
> [solution 1](01-one-fixed-nudge.md) describes the loop both solutions share.
> Read that page first.

## Introduction

This solution and [solution 1](01-one-fixed-nudge.md) differ by exactly one
decision, and this page is about what that decision is worth.

Solution 1 takes the single push that a printed rule names: the shortest push
that gives some glass room. This solution enumerates **every** push the
geometry will allow, hands the whole list to a model that scores each one, and
makes the push the model puts first. The model can never add a push to the list
and can never bring back one the geometry refused, so a wrong answer from it
costs one wasted push and nothing worse. That arrangement — generate with
geometry, filter with safety rules, then rank with something fitted — is the
careful way to use a model in a cell where a bad motion breaks glass.

So the question this page answers is **whether choosing from the whole set of
legal pushes beats taking the first one a rule names.**

The answer on the tables that count is **no, and by a clear margin.** The
ranked chooser separates seven tables where the plain rule separates ten, and
frees nineteen glasses where the plain rule frees twenty-five. It does that
with strictly more machinery for the same task. Most of this page is about
where that loss actually comes from, because a result like this is only useful
once it is explained.

**No glass's size appears below**, as everywhere in this project. The numbers
quoted belong to the hand, to the cell, or to a results file.

## A film of one table

Here is this solution clearing one table, recorded in the simulator and playing
at one and a half times real speed.

[Watch the film (23 s)](../../../videos/04-clear-the-table/02-geometry-ranked.mp4)

It is table 10001, the one table every solution in problem 4 is filmed on.
[The comparison page](../../../04-clear-the-table/results/README.md#a-film-of-each-solution)
says how it was chosen, and [the reference's film](01-one-fixed-nudge.md#a-film-of-one-table)
is the one to watch beside it.

The pair makes this page's measurement something to look at rather than only
read. Both solutions separate this table and neither breaks anything, so by the
scorecard they drew. But this one spends **five pushes and thirty-five arm
seconds** where the reference spends three and twenty-eight. That is the same
difference perfect play reports over all fifty held-out tables, where the
printed rule separates thirty-four of them with eighty-six pushes and this
chooser separates twenty-nine with a hundred and ten. The trees pick a
different push, and the different push is not a better one.
[The comparison page](../../../04-clear-the-table/results/README.md#what-was-possible-and-how-far-short-each-row-fell)
sets those two measurements side by side.

One thing the corner picture shows better than any paragraph is what a look
costs here. Several times the jaw ends up close to a glass, and the corner
fills with that one glass while the rest of the table falls outside the frame.
The solution is not being careless when it then drives somewhere else to look
again; it has no other way to see what it is standing next to.

## What it is made of

Almost nothing here is new, and that is the point of it.

**The loop is solution 1's**, and not a copy of it: the ring of stands, the
merged belief, the ranging push that finds the glass because there is no force
sensor to feel for it, the test push that asks whether the glass slides, and
the rule for saying the table needs nothing more. One method of solution 1's
own loop was turned into a named step so that this solution could replace it,
and a test checks that every other step is literally the same object, so
nothing can later be copied across and quietly changed in the middle.

**The candidate set and the model are problem 3's**, also borrowed. Problem 3's
second solution already had the enumerator that writes down every legal push,
the eight numbers that describe a push to the model, and the fitted trees. The
trees are loaded from the file problem 3 fitted and are **never fitted again
here.** If they were refitted, a difference between problem 3's result and this
one could be the fit rather than the problem, and the comparison would stop
meaning anything.

**One thing about the model's inputs changes, and it had to be checked.** Three
of the eight numbers describe a glass's neighbours — how the push meets the
nearest neighbour's edge, how much room the destination would have, and how
many neighbours are within reach. Problem 3 computed them over the whole table,
because its overhead camera handed the whole table over. Problem 4 has no such
camera, so here they are computed over the table **as the arm believes it**,
which is every glass it has seen so far and no more. All eight still compute,
for two reasons: the inputs are relations rather than addresses, so a relation
measured over part of a table is still a number, and the solution sweeps the
whole ring before it decides anything, so the belief it hands the model is
usually the whole table anyway. The belief can still be wrong, and then the
inputs are wrong — but solution 1's chooser works from the same belief, so the
two solutions are wrong in the same way and the comparison between them stays
fair.

## What it scored

The tables from ten thousand upwards are the measurement, walked once and never
tuned against. Fifty are offered in order, with fifteen arm minutes for the
whole queue, and each table may spend as much of what is left as it needs.
[Solution 1](01-one-fixed-nudge.md) walked the same queue with the same budget.

| | Ranked | Solution 1 |
|---|---|---|
| Tables attempted | **25** of fifty | 26 of fifty |
| Glasses on them | 98 | 102 |
| Tables separated, with nothing broken | **7** | **10** |
| Tables failed by a glass going over | 0 | 0 |
| Tables left crowded | 18 | 16 |
| Glasses broken | 0 | 0 |
| Glasses pickable | 38 at the start, **57** at the end | 39, **64** |
| Glasses it freed | **19** | **25** |
| It said it had finished | on 24 tables | on 24 tables |
| Said finished while still crowded | 17 | 14 |
| Paths the interlock refused | 0 | 0 |
| Arm time spent | almost exactly the 900 given | almost exactly the 900 given |
| Arm time for a table it separated | 41.7 s | 43.6 s |

## Why neither score has a spread

Both solutions walked the queue three times, as the examiner asks of everyone,
and **every count above is identical on all three walks** — table by table,
down to the hundredth of an arm second and the exact number of answers. There
is nothing to report as a spread, and reporting "± 0" would claim a variation
that was measured and came out at zero, where the truth is that neither
solution has anything to vary.

Given a table, each always answers the same way. Solution 1 computes its push.
This one enumerates the candidates in a fixed order, scores each with trees
that are loaded from a file and never refitted, and takes the first on the
sorted list. **A fitted model is not the same thing as a random one**: these
trees are a frozen function, and asking them the same question twice gives the
same answer twice.

The repeats exist for the solutions that come after these two. A policy of the
modern sort draws its action from a distribution rather than computing it, so
it can act differently on the same table, and its training carries a random
seed as well, so the same method trained twice is two policies of different
quality. That variation can be larger than the gap between two methods, which
is why a result quoted without a spread is not a result and a method that wins
by less than its own spread has not been shown to win. For these two solutions
the three walks are a check that the measurement reproduces. The one figure
that does move is the laptop time spent thinking, by about a fifth of a second
over twelve, and that measures the computer rather than the method.

## Where the loss comes from

Six glasses and three tables separate the two solutions. The per-table rows say
where they went, and the first thing they rule out is the obvious explanation.

### It is not that it reaches fewer tables

Both solutions spend essentially the whole fifteen minutes, so what sets the
length of the queue is what a table costs them, and this solution does cost
more: over the twenty-four tables both of them walked to their own finish, it
spends about thirty-four arm seconds more than solution 1, which is the same
four per cent its tuning run found. That is why it reaches twenty-five tables
where solution 1 reaches twenty-six.

**But the twenty-sixth table was worth almost nothing.** Solution 1 reached it
with a couple of seconds left, made three answers, and freed no glass on it.
The table before it is where the queue length did cost something: solution 1
arrived there with about thirty-eight seconds of budget and freed one glass,
while this solution arrived with under five seconds and could not. So **one**
of the six glasses is owed to the shorter queue, and **none of the three tables
is.**

### It is not the clock, the interlock, or a broken glass

All three are zero or nearly so for both solutions. Nothing was toppled, the
cell never refused a path, and every one of the tables the two solutions
disagree about ended with the solution saying it was finished rather than with
the clock stopping it. Whatever went wrong, it went wrong while the solution
still had time and still believed it was working.

### It is five tables out of twenty-five, and it wins one of them

Both solutions reached the same first twenty-five tables, and both declared
themselves finished on exactly the same twenty-four of them. On twenty of the
twenty-five the outcome is the same, and five of those twenty cost each
solution a single sweep and nothing else, because neither chooser found
anything it was willing to push — on those tables the two solutions are the
same program. The entire difference sits in five tables.

| table | solution 1 | the ranked chooser |
|---|---|---|
| 10,006 | left crowded, 1 glass freed | **cleared**, 2 freed, and in less time |
| 10,008 | **cleared**, 2 freed | left crowded, 0 freed, and it stopped sooner |
| 10,014 | **cleared**, 3 freed | left crowded, 1 freed, in the same time but with more answers |
| 10,015 | **cleared**, 3 freed | left crowded, 2 freed, and it stopped sooner |
| 10,017 | **cleared**, 2 freed | left crowded, 1 freed, and it spent longer |

Eleven glasses against six on those five tables, plus the one glass owed to the
shorter queue, is the six. On the twenty-five tables both solutions reached,
the share of glasses pickable at the end is 0.643 for solution 1 against 0.582
for this one.

### "Said done while crowded" is the same fact counted twice

Seventeen against fourteen looks like a second failing — as though this
solution gave up on more tables than solution 1 did. It is not. Both declared
themselves finished on twenty-four tables, and a declared table is either
cleared or still crowded, so twenty-four is ten and fourteen for solution 1,
and seven and seventeen here. **The three extra crowded finishes are the three
lost tables**, seen from the other side.

That also means the stopping rule is not the culprit. It is solution 1's own
rule, borrowed unchanged: both solutions stop when their chooser has no push
left that it is willing to make, and both sweep the whole ring again before
saying so. What differs is the arrangement the rule is asked about when it
fires.

### It does not simply give up earlier either

On two of the four tables it loses, it does stop sooner than solution 1. On the
other two it works **longer and achieves less**: on one it makes three more
answers in the same arm time and frees two fewer glasses, and on another it
spends five seconds more and frees one fewer. So neither "it quits early" nor
"it is too slow" covers the result on its own.

### Its cheaper average is an illusion

The card says this solution spends 41.7 arm seconds on a table it separates
against solution 1's 43.6, which reads as if it were the quicker of the two. It
is not. That average is taken over successful tables only, so the expensive
tables this solution lost drop out of it: the most expensive table of the whole
queue took about ninety-four seconds, and solution 1 cleared it and carries
that cost in its average, while this solution spent the same ninety-four
seconds there, did not clear it, and carries nothing. **On the six tables both
of them clear, this solution is slower by twenty-nine per cent**, and it uses
nearly a fifth more answers.

## Why the ordering costs tables here when it cost nothing before

The tuning run measured the ordering on its own, by running the identical loop
over the identical candidate set with the printed rule picking instead of the
trees. Over the eighty-five decisions where any candidate existed, the model
picked a push the rule ranks below its own on **seventy** of them — and every
table still ended in the same arrangement. The conclusion written down then was
that the model disagrees constantly and changes nothing.

The held-out queue shows that the second half of that sentence was a fact about
the tables, not about the model. Those tuning tables were drawn before the draw
was simplified, and **none of them could be separated at all**, even by a
chooser given true positions, exact pushes and unlimited pushes. On a set of
tables where no ordering can win, every ordering is equally good. On a set where
ten tables of twenty-six are winnable, a worse ordering has something to spoil
— and the same disagreement that was free before now costs three tables.

**What the model learned is which glass is risky, not which push helps.** Two
of its eight inputs carry four fifths of the importance in the fit: how high
the push is relative to the height at which that glass would topple, and how
wide the glass's foot is. Both are about whether the glass would go over.
Neither is about whether the push leaves the glass with room. So the model is a
good judge of danger and was never asked to be a judge of usefulness, and
sorting by danger is harmless when nothing can be won and harmful when
something can.

The shape of the losses fits that reading. Nothing toppled, the cell never
refused a path, and not one table was lost to a safety decision — the glasses
were simply left where the chosen pushes put them.

## What these rows cannot settle

This much is measured. What is **not** recorded is which push was chosen on
each answer, which glass it was for, whether that glass gained room because of
it, how many of its allowed tries a glass had already spent, and the reason
each glass was finally left alone. Without those, three readings of the five
divergent tables fit the evidence equally well, and they are not exclusive:

- the model's pick is legal but too slight to free its glass, so the glass uses
  up the small number of tries the loop allows it and is then left alone. The
  table where more answers in the same time freed fewer glasses has that shape.
- the model's pick sends a glass somewhere that is clear on the believed table
  but crowds a third glass, so the table never settles. The extra time spent on
  the tables both solutions clear has that shape.
- the model's ordering frees the easy glasses first and leaves the hard one
  surrounded, by which time there is nowhere for the hand to come in.

**None of these is asserted here, because the rows cannot tell them apart.**
What would settle it is one small measurement: a record, for the five tables
above, of every answer — the glass, the push, whether that glass gained room,
and why each glass was finally left — set beside solution 1's record of the
same table. It needs no new machinery, because the tuning run already keeps the
reasons a glass was left; the held-out rows simply do not carry them.

## Where it is strong and where it breaks

**The learned part sits where it can do least harm.** Geometry proposes, the
safety rules refuse, and only then does the model sort. A wrong answer costs
one push. This is the opposite arrangement from a policy that emits the motion
itself, where a wrong answer is carried out.

**It can say why a glass was left, which solution 1 cannot.** The printed rule
throws its candidates away as it goes, so every glass it could not place is
reported the same way. Keeping the candidate set separates two quite different
cases: a glass with no legal push at all, which is genuinely hemmed in, and a
glass whose every legal push was too slight to free it. On the tuning tables
those came out as eight against fifty-nine, which says the usual trouble is not
that the table is full but that the allowed pushes are too small to matter.
That is a different problem and it points at a different fix.

**It is beaten on cost as well as on result.** It spends four per cent more arm
time per table and nearly a fifth more answers on the tables it clears, for a
worse score. Problem 3 found the same thing in gentler form — there the ranked
chooser reached the same tables by a more expensive route — and problem 4
sharpens it, because here the route leads somewhere worse.

**It inherits every limit of the loop it borrows.** It has the same camera on
the arm, the same ring of stands, the same ranging push in place of a force
sensor, and the same bound on how deep the fingertips may reach while the
camera cannot tell a touched glass from a leaning one.

**One of its eight inputs is no longer about the task.** The distance from a
push's destination to the drying rack is still a number this cell can compute,
because the rack is part of the cell, but problem 4 never racks a glass. It
carries little weight in the fit, and it is left in place because dropping an
input would mean refitting, and then a difference from problem 3 could be the
fit rather than the problem.

## What this tells a later solution

**A model that ranks safely is not the same as a model that helps.** This one
was fitted to a question it answers well — which glass is dangerous to push —
and then used to answer a different one. Any later solution that wants a model
to choose pushes should be clear about which of those two questions it was
fitted to, and should expect that ordering by the first costs tables as soon as
the tables are winnable.

**Adding machinery to a loop can make it worse, and the examiner is what shows
it.** This solution is solution 1 with one step replaced, and nothing else
about it differs. Because the two were offered the same tables in the same
order with the same budget and were marked the same way, the three lost tables
can be laid at that one step. That is the whole reason for keeping the edges of
the measurement fixed.

---

← [Solution 1 — one fixed nudge](01-one-fixed-nudge.md) ·
[Problem 4 — clear the table](../problem.md) ·
[The examiner](../the-examiner.md)
