# Problem 4 — the six solutions side by side

This page compares every solution to problem 4. Each one is given a table with
some glasses standing too close together for the gripper to get round one
without fouling its neighbour, and it has to drag them apart until every glass
has room and then say that it has finished. Nothing is lifted and nothing is
racked, so what is cleared is the crowding rather than the table. By the end of
this page you will know what each of the six achieved, how far short of the
best possible result each one fell, and which three columns mislead if you read
them on their own.

> **A note on links.** This page belongs to the first cell, and some of the documents it
> cites, such as *what changed* and *the examiner*, were removed when `docs/` was rewritten for
> the whole-arm cell. Those links open the documents as they stood before that, on GitHub.

> **A note on row 5.** Solution 5, the borrowed model with nothing fitted, has been retired
> and replaced in the line-up by reinforcement learning in the
> [whole-arm cell](../full-arm/README.md), which is a different cell and is not on this page.
> Its row is kept below, marked, because the fitted model in row 6 is compared against it and
> every number was true when it was measured.

Problem 4 is problem 3 with two assumptions taken away. The camera above the
table is gone, so the arm carries its own camera and looking costs motion and
time. The push-by-push hand-over is gone too, so a solution runs continuously
and declares itself done, and the table is judged by the arrangement it was
left in. [The examiner](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/the-examiner.md) describes
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

Every row is the solution as it stands now. The six were measured once, then a
set of changes was made to the three that were learning something and failing,
and then they were measured again;
[what changed](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/what-changed.md) records each
change beside the measurement that justified it, including the three that were
tried and thrown away.

| | tables attempted | tables separated | failed by a topple | glasses | glasses freed | pickable share | glasses broken | said done while crowded | thinking an answer |
|---|---|---|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | 26 | 10 | **0** | 102 | +25 | **0.627** | **0** | 14 | 15 ms |
| [2 geometry ranked](../02-geometry-ranked/) | 25 | 7 | **0** | 98 | +19 | 0.582 | **0** | 17 | 15 ms |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 14 | **0** | 1 | 52 | **−1** | **0.359** | 1 | 9 | 21 ms |
| [4 a world model](../04-a-world-model/) | **39** | **14** | **5** | 155 | **+33** | 0.550 | **5** | 22 | **11 ms** |
| 5 SmolVLA as it downloads (retired) | **11** | 1 | **0** | 40 | +2 | 0.439 | **0** | 9 | 280 ms |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | **11** | **0** | **0** | 41 | 0 | 0.405 | **0** | 9 | **282 ms** |

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

### The same tables, for the rows that reached different distances

The table above has a difficulty in it that is easy to miss. Because the clock
belongs to the queue, a faster solution reaches further down the list, and the
tables it reaches there are not the tables the slower rows were scored on. So
the fourth row is being credited with thirty-nine tables while three of the rows
are credited with eleven to fourteen, and the numbers are not of the same thing.

The repair is to cut every walk to the same prefix of the queue and count only
those tables. The queue is always walked in order, so the first ten tables of
one walk are exactly the first ten tables of every other. Below are the ten
tables that all six solutions reached, and then the twenty-six that the fixed
nudge reached, which is the prefix the two leading rows share.

| the first ten tables | tables separated | glasses freed | pickable share | glasses broken |
|---|---|---|---|---|
| 1 one fixed nudge | 5 | +11 | 0.703 | 0 |
| 2 geometry ranked | 5 | +10 | 0.676 | 0 |
| 3 imitation, ACT | 0 (0 to 2) | 0 (−2 to +4) | 0.351 | 1 |
| 4 a world model | 6 (5 to 6) | +12 (+11 to +13) | 0.730 | 0 (0 to 1) |
| 5 SmolVLA as it downloads (retired) | 1 (0 to 1) | +2 (0 to +2) | 0.459 | 0 |
| 6 SmolVLA fine-tuned | 0 | 0 | 0.405 | 0 (0 to 1) |
| perfect play | 8 | +16 | 0.838 | 0 |

| the first twenty-six tables | tables separated | glasses freed | pickable share | glasses broken |
|---|---|---|---|---|
| 1 one fixed nudge | 10 | +25 | 0.627 | 0 |
| 2 geometry ranked | 7 of the 25 it reached | +19 | 0.582 | 0 |
| 4 a world model | 10 | +24 (+22 to +29) | 0.578 | 2 (1 to 3) |
| perfect play | 16 | +40 | 0.775 | 0 |

Both tables count a forfeited table the way the card does: a table that lost a
glass is left out of the pickable count at both ends, while every glass on it
still counts in the total the share is taken out of.

On the ten tables the three competent solutions are close together: the world
model separates six where the two geometry solutions separate five, and it frees
twelve glasses to their eleven and ten, with one of its three walks losing a
glass. On the twenty-six they are level. The world model separates ten tables
and so does the reference, it frees twenty-four glasses to the reference's
twenty-five, and it breaks two glasses where the reference breaks none. So the
place where it is clearly ahead is not the shared prefix but the clock, because
it wins a table for about twenty-five arm seconds against the reference's
forty-four, which is why it reaches thirty-nine tables and separates fourteen in
the time the reference spends on twenty-six.

**Those two broken glasses are a price that was paid on purpose**, and
[what changed](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/what-changed.md) records the choice.
The world model is now fitted on twice the random pushes and charged ten times as
much for a topple it fails to predict, and that pair was chosen on a hundred and
fifty tables below the held-out line under the real clock, where it separated
more tables and broke *fewer* glasses than the fit before it. On the held-out
queue it breaks more. The two instruments disagree, the change was kept because
the choice has to be made below the line, and these rows are what the
disagreement costs.

**The three picture-driven rows are closer together than their columns suggest.**
On the ten tables they all reached, the imitation policy ends level on glasses
with room and breaks one, the borrowed model frees two and breaks none, and the
fine-tuned one frees and breaks nothing. None of them separates a table except
by luck, and the differences between them are inside their own spreads: the
imitation policy's own spread runs from two glasses lost to four freed.

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
| 3 imitation, ACT | 0 of 14 | 10 | 0.359 | 0.788 |
| 4 a world model | 14 of 39 | 26 | 0.550 | 0.813 |
| 5 SmolVLA as it downloads (retired) | 1 of 11 | 9 | 0.439 | 0.850 |
| 6 SmolVLA fine-tuned | 0 of 11 | 9 | 0.405 | 0.850 |

**The two leading rows reach between a half and five eighths of the ceiling on
tables, and about three quarters to four fifths of it on glasses.** So the task
is neither solved nor impossible, which is what a useful measurement looks
like. Note that the ceiling is a ceiling on the *arrangements* and not on the
queue, because the fifteen arm minutes are exactly what perfect play removes.
Nothing in the table above could be reached inside the budget.

## Three columns that mislead on their own

**Tables attempted is not a score.** A solution that gives up on every table
instantly would reach the most of them, which is why the fine-tuned model
reaches eleven and the world model thirty-nine while neither number says which
is better. Read it beside tables separated, and remember that it counts the tables
the arm worked on rather than how far down the list the solution got: at the end
of a queue a walk can pass through tables it cannot afford and still find a
later one cheap enough to answer once.

**The pickable share has a different denominator in every row.** A solution
that reached ten tables is being scored over the glasses on those ten tables,
and a solution that reached forty over the glasses on forty. The two tables
above are what make the rows comparable, because they use the same prefixes.
The clearest case is the world model. On the card its share is 0.550 against the
reference's 0.627, a gap of about eight hundredths; on the twenty-six tables the
two of them share it is 0.578 against 0.627, a gap of about five. The card's
version of the gap is partly the thirteen extra tables the world model reached
and not a difference in how well the two behave.

**A share can be high because nothing was touched.** Of the glasses counted in
a share, the ones that already had room when the table was drawn cost a
solution nothing. The fine-tuned borrowed model scores 0.405 having freed no
glass at all, so every glass in that share was free; the fixed nudge scores
0.627 having freed twenty-five, so a third of its share was earned. Always read
the share beside the glasses-freed column, which is the part a solution is
responsible for.

**Zero glasses broken is only praise beside work done.** Four rows break
nothing. Two of them do so while separating ten and seven tables; the other two
do so while freeing two glasses and none, which means they are harmless rather
than safe.

## What the six results say

**The world model is level with the geometry reference on the tables they both
reach, and ahead of it on the clock.** On the twenty-six tables they share it
separates ten tables to the reference's ten and frees twenty-four glasses to its
twenty-five, which is a tie. What it does better is spend the budget: a separated
table costs it about twenty-five arm seconds against the reference's forty-four,
so inside the same fifteen minutes it reaches thirty-nine tables and separates
fourteen. What it does worse is keep the glasses standing, because it breaks five
over the queue where the reference breaks none. The first measured walk of this
solution broke eight glasses and separated eleven of thirty-two, so the long
story of it is not that it learned to choose better pushes but that it stopped
destroying the tables it was already choosing well on, and that it has given
some of that back in exchange for tables.

**Ranking the candidate pushes makes things worse, and it is the ordering
itself.** The ranked chooser enumerates every safe push and sorts them with
fitted trees instead of taking the first safe push the printed rule names. It
separates seven tables against ten and frees nineteen glasses against
twenty-five. Perfect play settles where that comes from, because with the arm
taken away and no clock the printed rule separates **thirty-four** of the fifty
tables while the fitted ranker separates **twenty-nine**, and the ranker needs
a hundred and ten pushes to the rule's eighty-six. So the ordering is worse at
choosing even when nothing can go wrong in carrying it out. It is not that the
trees were fitted on the wrong question: their label is the room the whole table
gained from a push, and on problem 3's own per-decision test they predict it
better than the printed rule does. What differs is the tables they were shown.
Problem 3 racks every glass that already has room before it plans, so a glass
with room was never on a training table; problem 4 lifts nothing, so every
glass with room stays where it is and gets in the way. The ordering is being
asked about tables of a kind it never saw.

**The three solutions that answer from a picture are now nearly harmless, and
between them they free one glass.** That is a poor result, and it is a very
different poor result from the one the first walk produced: then the three of
them freed nothing at all and broke twenty-eight glasses between them, and two
of the three never said a table was finished because a glass went over before
they could. Now the imitation policy ends its queue one glass down and breaks
one, the borrowed model run as it downloads frees two and breaks none, and the
fine-tuned one frees and breaks nothing.

**One of those three is doing the task and two are not, and the columns do not
show it.** The imitation policy chooses a glass, tests whether it slides, and
pushes it, so the glasses it frees are the glasses it chose. The borrowed
model's two freed glasses come from shoves that happened to go a helpful way: it
comes down at no glass in particular, and the arithmetic afterwards reads back
which glass the path came nearest. Equal numbers in a column can be earned or
stumbled into, and the only way to tell is to read what the solution was trying
to do.

**Looking is most of what the task is, so looking is what gets learned.** With
the camera on the arm, four of the teacher's five answers move the arm only to
see. When the picture does not say whether the teacher would look or push, the
answer that minimises the average error is the looking answer, and the average
of the teacher's answers is exactly what fitting on them produces. This is the
single finding that explains all three of the picture-driven rows, and the two
repairs for it are the two things that moved them: the imitation policy was
split into a part that decides which kind of answer is wanted and a part that
draws it, and the fine-tuned model was fitted on a mixture of looks and pushes
weighted evenly instead of on the teacher's own four-to-one.

**Fitting the borrowed model on this cell buys work and does not buy care.**
Its own page measures the pair it exists for: the same weights, the same loop and
the same twenty tables, with and without this cell's demonstrations. Fitted, it
draws paths less than half as long in steps a third as long — the length and
speed of its teacher's pushes — comes down to pushing height nearly twice as
often, and frees two glasses where the untrained model frees none. It also
topples two where the untrained model topples none, so its share comes out
slightly *lower* than the model it started from. A thousand steps over three
hundred tables taught it to go and act on a glass, and not to do so without
sometimes putting it over.

**The untrained borrowed model is worse here than in problem 3, and the camera
is not why.** The sensitivity check separates the two things that changed. The
wrist picture moved its answers by nothing. What moved them is the jaw pose it
is told about: problem 3 asked it with the jaw parked above travel height,
which clipped to the top of the range the reading can express, while problem 4
tells it where the jaw really is. Its paths dropped about seventy millimetres
as a result, which puts the hand within a millimetre of pushing height while
the path still travels most of the way across the zone. On the first walk that
was the most destructive behaviour in the problem, twenty glasses broken; it is
now harmless, because the solution's own clearance arithmetic lifts a path that
would travel across the table at the height of the glasses' rims.

**Thinking time divides the six into two groups.** The four solutions that
compute or fit something small answer in ten to nineteen milliseconds. The two
borrowed foundation models need about two hundred and eighty milliseconds an
answer, which is fifteen to thirty times more, for results that are worse on
every column of work done. That gap is not part
of the score, because the budget is the arm's time, but it is what decides
whether a method could run on a real arm at all.

## A film of each solution

A table of totals says what happened and never why, and on this page the gap
between the two is wide. Three of the six leave the filmed table exactly as they
found it, and that one result covers a policy that says the table is finished
after nine answers, a policy that crosses the table sixteen times without ever
coming down, and a policy that comes down once in the wrong place. So each
solution was also filmed clearing one table.

**Every film is of the same table, and it was chosen by a rule.** The table has
to be one that all six solutions reached, which puts it inside the first ten of
the queue, because the shortest of the six walks got through ten tables. It also
has to be a table where something happens: on most of those ten the geometry
reference looks round the table, finds no push it believes in and says it is
finished. Table 10001 is the first that passes both. It holds four straight
glasses, two of which have room at the start.

**What a frame shows.** The large picture is the table from the arm's side of
it. The corner holds the last picture the arm's own camera gave the solution,
and the corner is the half worth watching, because it is everything the
solution knew when it chose what to do next. A line across the top names the
answer being carried out and says whether the hand comes down low enough to
touch a glass -- a push -- or stays above the glasses -- a look. That is the
same test [`bench/stopping.py`](../bench/stopping.py) uses to decide when a
policy with no word for "finished" has stopped proposing pushes.

| | the film | answers | of them pushes | arm seconds | how it ends |
|---|---|---|---|---|---|
| 1 one fixed nudge | [17 s](../videos/01-one-fixed-nudge.mp4) | 26 | 3 | 28 | separated |
| 2 geometry ranked | [23 s](../videos/02-geometry-ranked.mp4) | 32 | 5 | 35 | separated |
| 3 imitation, ACT | [5 s](../videos/03-imitation-from-demonstrations.mp4) | 9 | 0 | 9 | said done, nothing freed |
| 4 a world model | [11 s](../videos/04-a-world-model.mp4) | 20 | 1 | 22 | separated |
| 5 SmolVLA as it downloads (retired) | [53 s](../videos/05-smolvla-as-it-downloads.mp4) | 16 | 0 | 71 | said done, nothing freed |
| 6 SmolVLA fine-tuned | [40 s](../videos/06-smolvla-fine-tuned.mp4) | 17 | 1 | 56 | said done, nothing freed |

Read down the "of them pushes" column and the problem is in front of you.
**The three solutions that separate this table are the three that push it, and
none of them pushes much.** The world model separates it with one push in
twenty-two arm seconds, the reference with three in twenty-eight, the ranked
chooser with five in thirty-five. Everything else in those films is the arm
driving somewhere to see, which is what problem 4 charges for and problem 3 gave
away. The three that free nothing give nine, sixteen and seventeen answers and
come down at a glass once between them.

**These films are also the clearest picture of what the changes to this problem
did.** Filmed before them, the two borrowed models each ended this table with a
glass on its side, and the imitation policy hovered over it with the fingers at
the height of the rims. All three now cross the table well clear of the glasses
and then say, wrongly but harmlessly, that the table needs nothing more. The
work that is still missing is visible in the same films: none of the three ever
settles behind a crowded glass and shoves it.

**The films are fresh runs and not recordings of the scored walks.** Nothing of
a walk is kept but its numbers, so a film has to be made by running the table
again. The two geometry solutions answer the same way every time and so film
exactly what they were scored doing. The other four draw from noise or are one
of three fits, so each of those films is one run: it shows what the solution
does, and the numbers written on its own last picture are its own rather than
the middle of three walks. On this particular table the four are nearly steady:
the world model separates it in all three scored walks, and the two borrowed
models leave it exactly as they found it in all three. The imitation policy is
the exception, and it is worth knowing — two of its three fits leave the table
alone, and the third takes it from two glasses with room to none.

Each film is made by [`results/films.py`](films.py), one solution to a process,
and `make films` makes all six.

## Where to read more

Each solution's folder has a `README.md` of its own, which gives its spread,
its own selection measurements on tables below the held-out band, and what it
found out about problem 4 while being built. Solution 5 was retired with its
folder, so its page is linked as it stood before it was removed.

1. [One fixed nudge](../01-one-fixed-nudge/README.md)
2. [Geometry ranked](../02-geometry-ranked/README.md)
3. [Imitation from demonstrations](../03-imitation-from-demonstrations/README.md)
4. [A world model](../04-a-world-model/README.md)
5. [SmolVLA as it downloads](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/solutions/05-smolvla-as-it-downloads.md)
6. [SmolVLA fine-tuned](../06-smolvla-fine-tuned/README.md)

`ceiling.json` beside this page holds the perfect-play measurement, table by
table and as a running total, which is where the ceiling columns come from. It
is perfect play with the printed rule choosing. `ceiling-ranked.json` is the
same fifty tables with the fitted trees choosing instead, and the pair is what
the paragraph above about the ordering is read from.

Problem 3's own comparison is at
[`03-push-glasses-apart/results/`](../../03-push-glasses-apart/results/README.md).
The two scorecards answer different questions and both are worth keeping:
problem 3's says what one change did to a table, and problem 4's says what the
arm would do on its own.
