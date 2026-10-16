# Problem 4 — the six solutions side by side

This page compares every solution to problem 4. Each one is given a table with
some glasses standing too close together for the gripper to get round one
without fouling its neighbour, and it has to drag them apart until every glass
has room and then say that it has finished. Nothing is lifted and nothing is
racked, so what is cleared is the crowding rather than the table. By the end of
this page you will know what each of the six achieved, how far short of the
best possible result each one fell, and which three columns mislead if you read
them on their own.

Problem 4 is problem 3 with two assumptions taken away. The camera above the
table is gone, so the arm carries its own camera and looking costs motion and
time. The push-by-push hand-over is gone too, so a solution runs continuously
and declares itself done, and the table is judged by the arrangement it was
left in. [The examiner](../../docs/04-clear-the-table/the-examiner.md) describes
both changes and how a walk of tables is marked.

## What every row was measured on

Every solution walked the same **held-out queue**: fifty tables offered in
order from table ten thousand, with **fifteen minutes of arm time for the whole
queue**, walked three times. No solution saw those tables while it was being
built or fitted.

Three things about that arrangement matter for reading the table below.

**The budget belongs to the queue and not to a table.** Each table may spend as
much of what is left as it needs, so a solution that works slowly reaches fewer
tables. This makes speed part of the score instead of a separate column.

**Arm time is simulated seconds of the arm moving**, added up from the paths
actually carried out, and not seconds of laptop time. Two solutions that make
the same motions occupy a real cell for the same length of time, whatever
computer they ran on. Thinking time is recorded separately, in its own column,
because the arm is not the thing that was slow.

**A toppled glass forfeits its table.** A table that lost a glass counts for
nothing at either end, so breaking a glass is never cheaper than leaving the
table alone. Every glass on it is still counted among the glasses the share is
taken out of.

## The results

Each row is one solution, and each number is the middle of the three walks,
read from that solution's own `results.json`. Bold marks the best and the worst
value in a column.

| | tables attempted | tables separated | failed by a topple | glasses | glasses freed | pickable share | glasses broken | said done while crowded | thinking an answer |
|---|---|---|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | 26 | 10 | **0** | 102 | 25 | **0.627** | **0** | 14 | 15 ms |
| [2 geometry ranked](../02-geometry-ranked/) | 25 | 7 | **0** | 98 | 19 | 0.582 | **0** | 17 | 15 ms |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 10 | **0** | **0** | 37 | **0** | 0.400 | **0** | 9 | 16 ms |
| [4 a world model](../04-a-world-model/) | **32** | **11** | 7 | 125 | **29** | 0.560 | 8 | 13 | **6 ms** |
| [5 SmolVLA as it downloads](../05-smolvla-as-it-downloads/) | 15 | **0** | **14** | 57 | **−1** | **0.018** | **20** | **0** | **776 ms** |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | **8** | **0** | 6 | 29 | **0** | 0.103 | 8 | **0** | 279 ms |

**Tables separated** is the clean pass: every glass on the table has room for
the hand, and nothing fell. **Glasses freed** is how many more glasses had room
at the end than at the start, which can be negative because a solution is free
to push a glass into its neighbour. The **pickable share** is the glasses that
ended with room out of every glass on every table attempted, and it is the
partial credit that lets two solutions be told apart even when neither
finishes many tables.

The first two rows carry no spread because they choose nothing at random: given
a table, each always answers the same way, so all three of their walks are
identical table for table. The other four draw from noise or from a different
fit each walk, and each one's own page gives the spread of every number.

## What was possible, and how far short each row fell

A result of ten tables separated means nothing until you know how many of those
tables could be separated at all. So perfect play was measured on the same
fifty tables: the arm is taken away entirely, the chooser is given the true
positions, every push lands exactly where it aimed, and there is no clock. What
comes back is a property of the draw and not a solution's score, which is why
it is the one measurement allowed to touch the held-out tables.

Because the queue is walked in order, a solution that reached twenty-six tables
reached the *same* twenty-six tables as any other solution that reached
twenty-six, holding the same glasses. So each row can be read against the
ceiling on exactly the prefix it reached.

| | tables separated | the ceiling | pickable share | the ceiling |
|---|---|---|---|---|
| 1 one fixed nudge | 10 of 26 | 16 | 0.627 | 0.775 |
| 2 geometry ranked | 7 of 25 | 15 | 0.582 | 0.765 |
| 3 imitation, ACT | 0 of 10 | 8 | 0.400 | 0.838 |
| 4 a world model | 11 of 32 | 21 | 0.560 | 0.808 |
| 5 SmolVLA as it downloads | 0 of 15 | 11 | 0.018 | 0.807 |
| 6 SmolVLA fine-tuned | 0 of 8 | 6 | 0.103 | 0.793 |

**The best row reaches about two thirds of the ceiling on tables and four
fifths of it on glasses.** So the task is neither solved nor impossible, which
is what a useful measurement looks like. Note that the ceiling is a ceiling on
the *arrangements* and not on the queue, because the fifteen arm minutes are
exactly what perfect play removes. Nothing in the table above could be reached
inside the budget.

## Three columns that mislead on their own

**Tables attempted is not a score.** A solution that gives up on every table
instantly would reach the most of them, which is why the fine-tuned model
reaches eight and the world model thirty-two while neither number says which is
better. Read it beside tables separated, and remember that it counts the tables
the arm worked on rather than how far down the list the solution got: at the end
of a queue a walk can pass through tables it cannot afford and still find a
later one cheap enough to answer once.

**The pickable share has a different denominator in every row.** A solution
that reached ten tables is being scored over the glasses on those ten tables,
and a solution that reached thirty-two over the glasses on thirty-two. The
ceiling table above is what makes those comparable, because it uses the same
prefixes. The clearest case is the imitation policy: its share of 0.400 looks
respectable beside the world model's 0.560, but it freed **no glasses at all**,
so that 0.400 is entirely the glasses that already had room when the table was
drawn.

**Zero glasses broken is only praise beside work done.** Three rows broke
nothing. Two of them did so while separating ten and seven tables, and the
third did so while changing nothing on the table.

## What the six results say

**Geometry wins, and nothing that learns has beaten it.** The simplest
solution of the six — one push a table, chosen by arithmetic, with nothing
learned anywhere — separates ten of the twenty-six tables it reaches and breaks
no glass. This is the same conclusion problem 3 reached, and problem 4 reaches
it with the overhead camera taken away, which was the assumption most likely to
have been flattering the geometry.

**Ranking the candidate pushes makes things worse, and it is the ordering
itself.** The ranked chooser enumerates every safe push and sorts them with
fitted trees instead of taking the first safe push the printed rule names. It
separates seven tables against ten and frees nineteen glasses against
twenty-five. Perfect play settles where that comes from, because with the arm
taken away and no clock the printed rule separates **thirty-four** of the fifty
tables while the fitted ranker separates **twenty-nine**, and the ranker needs
a hundred and ten pushes to the rule's eighty-six. So the ordering is worse at
choosing even when nothing can go wrong in carrying it out. The trees were
fitted to judge whether a push would tip a glass, which is about risk, and not
whether a push would actually free one.

**The world model is level on tables and ahead on glasses, and breakage is
what holds it back.** It separates eleven tables against the fixed nudge's ten,
which is inside its own spread of eight to twelve, so the two are level rather
than ordered. It frees the most glasses of any solution and wins a table for
the least arm time, twenty-seven seconds against forty-four. But it breaks
eight glasses, and seven forfeited tables pay nothing at either end. Had those
tables merely been left crowded, its share would read about 0.62 rather than
0.56, which is the whole of the gap to the geometry.

**The three solutions that answer from pictures free nothing at all.** Between
them they separate no table and free no glass, and this is the clearest result
of the problem. The reason is the same in each case and it is not about aim. It
is about which of the teacher's two kinds of answer gets learned.

**Looking is most of what the task is, so looking is what gets learned.** With
the camera on the arm, four of the teacher's five answers move the arm only to
see. When the picture does not say whether the teacher would look or push, the
answer that minimises the average error is the looking answer, and the average
of the teacher's answers is exactly what fitting on them produces. The
imitation policy learned this most plainly: one of its three fits emits a chunk
of a single waypoint every time.

**The two problems' fits of the same borrowed model fail in mirror image.**
Problem 3's fit learned the pushing height and crashed down onto the glasses,
breaking far more than its untrained partner. Problem 4's fit learned the
looking height and sweeps over them, breaking eight where its untrained partner
breaks twenty. The fine-tuned model is therefore safer than the untrained one
and no more capable: the fit bought safety, not competence. Neither problem's
fit learned where to put the jaw **down**, which is the only thing the task
needs.

**The untrained borrowed model is worse here than in problem 3, and the camera
is not why.** The sensitivity check separates the two things that changed. The
wrist picture moved its answers by nothing. What moved them is the jaw pose it
is told about: problem 3 asked it with the jaw parked above travel height,
which clipped to the top of the range the reading can express, while problem 4
tells it where the jaw really is. Its paths dropped about seventy millimetres
as a result, which puts the hand within a millimetre of pushing height while
the path still travels most of the way across the zone. So it now reaches the
glasses without aiming at them, which is more destructive than never reaching
them at all.

**Thinking time divides the six into two groups.** The four solutions that
compute or fit something small answer in six to sixteen milliseconds. The two
borrowed foundation models need two hundred and seventy-nine and seven hundred
and seventy-six milliseconds an answer, which is fifty to a hundred and thirty
times more, for results that are worse on every column. That gap is not part of
the score, because the budget is the arm's time, but it is what decides whether
a method could run on a real arm at all.

## Where to read more

Each solution has a page of its own, which gives its spread, its own selection
measurements on tables below the held-out band, and what it found out about
problem 4 while being built.

1. [One fixed nudge](../../docs/04-clear-the-table/solutions/01-one-fixed-nudge.md)
2. [Geometry ranked](../../docs/04-clear-the-table/solutions/02-geometry-ranked.md)
3. [Imitation from demonstrations](../03-imitation-from-demonstrations/README.md)
4. [A world model](../../docs/04-clear-the-table/solutions/04-a-world-model.md)
5. [SmolVLA as it downloads](../../docs/04-clear-the-table/solutions/05-smolvla-as-it-downloads.md)
6. [SmolVLA fine-tuned](../../docs/04-clear-the-table/solutions/06-smolvla-fine-tuned.md)

`ceiling.json` beside this page holds the perfect-play measurement, table by
table and as a running total, which is where the ceiling columns come from.

Problem 3's own comparison is at
[`03-push-glasses-apart/results/`](../../03-push-glasses-apart/results/README.md).
The two scorecards answer different questions and both are worth keeping:
problem 3's says what one change did to a table, and problem 4's says what the
arm would do on its own.
