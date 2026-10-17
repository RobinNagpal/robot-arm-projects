# Solution 5 — a borrowed model, given the camera it was pretrained with

> **What it uses** — SmolVLA, a general robot policy of about 450 million
> parameters, taken from the LeRobot library exactly as it downloads. Nothing
> in it is fitted, trained or tuned in this cell. The join between what it
> emits and this cell's jaw is imported from problem 3 and is not re-chosen.
> **What it does** — it is shown the picture from the camera on the wrist, one
> sentence of instruction, and where the jaw is standing. It answers with a run
> of waypoints, and the cell carries them out.
> **How it differs from the others** — it is the only solution here whose every
> number comes from somewhere else, and the only one that was expected to do
> badly before anything was measured. Its value is not its score. It is the
> starting point the fine-tuned version is measured against.
> **What it costs** — no demonstrations, no labels and no fitting. It needs the
> library, two gigabytes of downloaded weights and a laptop. Its one real cost
> is time per answer: 776 milliseconds, against six for the solution that fits
> its own model here.

> **The cell is described once, in [the cell](../../the-cell.md).** What kind of
> model this is, where its competence comes from, how a run of actions is read
> as jaw waypoints and why the units of that reading matter so much is
> described once in
> [problem 3's page for the same model](../../03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md).
> This page covers only what problem 4 changes, and what problem 4 measured.

## Introduction

This page answers [problem 4](../problem.md) with a downloaded model, and it
reports the sharpest result in the problem so far: **giving the model the
camera a real robot actually carries made it much worse, not better.**

That needs saying carefully, because it is easy to draw the wrong lesson from
it. In [problem 3](../../03-push-glasses-apart/README.md) this same model was
shown a picture from a camera bolted above the table. It swept the jaw through
the air above the glasses and never came down to them, so it broke very little
and achieved very little: of the glasses it put on the drying rack, every single
one already had room before it started.

Problem 4 takes that overhead camera away. The arm carries its own camera on
the wrist, looking forward and down, which is the view almost every real robot
in the model's pretraining actually had. So the input this model is given in
problem 4 is **closer to its home ground** than problem 3's was, and the
prediction written down before the run was that its answers should therefore
look more like pushes.

Its answers did come down. They came down into the glasses. On its first walk of
the held-out queue it reached fifteen tables, separated none of them, broke
twenty of the fifty-seven glasses it met, and never once said that a table was
finished.

**It has since been measured again, with one thing added and nothing retrained,**
and the second card is the one this page reports beside the first. The thing
added is the clearance check every solution in this problem can run over its own
answer: a path that cannot be shown to reach only the glass it names is raised to
travel height, where it goes to the same place and touches nothing. With it, the
same weights on the same fifty tables break **no** glasses at all — and free no
glasses either. The model was never doing anything but travelling at the height
of the glasses' rims, and the check makes that visible instead of expensive.

By the end of this page you will know:

- how a policy that has no words for "I am finished" is allowed to say so
  anyway, and why that rule decides most of this solution's card;
- what the held-out queue measured, before and after the clearance check;
- why the answers came down, which turns out not to be the camera at all;
- why a path that reaches the table without aiming at anything is worse than a
  path that never reaches it;
- why the cell's own safety interlock could not prevent any of it, and what the
  solution's own check does that the cell's cannot;
- which of these conclusions the saved numbers support, and which still need a
  measurement.

Read [the examiner](../the-examiner.md) first. It defines what a solution is
shown, what it may answer, why saying "done" is part of the job, and what each
line of the card means.

## A film of one table

Here is the borrowed model on one table, recorded in the simulator and playing
at one and a half times real speed.

[Watch the film (53 s)](../../../videos/04-clear-the-table/05-smolvla-as-it-downloads.mp4)

It is table 10001 of the held-out fifty, the one table every solution in
problem 4 is filmed on, so it can be watched beside
[the geometry reference on the same glasses](01-one-fixed-nudge.md#a-film-of-one-table).
[The comparison page](../../../04-clear-the-table/results/README.md#a-film-of-each-solution)
says how the table was chosen. It is still much the emptiest of the six films,
and that is the result rather than a fault in the recording.

**Not one of its sixteen answers is marked a push.** The writing across the top
says of each answer whether the hand comes low enough to touch a glass, and
here it never does. That is the clearance arithmetic at work rather than the
model being careful: the paths the model draws come down to within a millimetre
or two of the pushing height, and almost every one of them is raised to travel
height before the arm moves, because it comes down at no glass in particular.
So what a viewer watches is the arm crossing the table over and over, well
clear of the glasses, in seventy-one arm seconds.

**The corner is often empty table.** Several of its answers leave the jaw
pointing at a patch with no glass in it at all, so the picture the model is
given for its next answer holds nothing to act on. A viewer can watch the
model asking for its next push from a view of bare table.

**It ends by saying the table is finished, with two of the four glasses still
short of room.** Sixteen answers in a row that could not touch a glass is what
the shared stopping rule reads as a policy saying it has nothing to do, and
that is an honest reading here. On the same table, before the clearance
arithmetic was added, this solution ended with a glass on its side. Counting
pushes was never what this solution needed; aiming them was.

## How a policy with no words for it says it is finished

Problem 4 asks every solution to declare a table finished. This policy cannot
utter that sentence. It answers with a run of waypoints and has no spare output
meaning "nothing here needs moving", and nothing it was trained on ever taught
it to produce one. Problem 3 never had to face this, because problem 3's shared
loop decided for every policy when a table was over.

So problem 4's bench holds one shared rule, and this solution uses it unchanged
rather than inventing a second one. The rule reads the declaration out of the
policy's own behaviour: **a policy that has stopped proposing pushes is saying,
in the only language it has, that it sees nothing worth doing.** Three answers
in a row that would not touch a glass are taken as the policy saying it is
finished. One would be too few, because a policy that draws its answer rather
than computing it will draw a stray one; three in a row from a policy that acts
at all is not a coincidence.

Everything then turns on what "would not touch a glass" means, and this is where
a fault was found and fixed. A waypoint carries a height, and that height is the
**middle** of the jaw: the fingers hang about seventy millimetres below it. The
first version of the rule compared the waypoint's own height against the height
the hand pushes at, and so a path that passed seventy millimetres above the
pushing height was recorded as quiet while the fingers were dragging through the
glasses underneath it. This solution is what found that, because it is the only
solution that spends its whole time in that band. One of its early runs broke a
glass while every single answer was being recorded as quiet.

The rule now measures from where the hand really is, and asks whether any part
of the hand on a path comes low enough to touch the tallest glass the solution
has so far measured on that table. No glass size is written down to do it: the
height is one the arm measured during the run, and a solution that has seen
nothing yet falls back to the hand's own pushing height, which belongs to the
gripper.

**The two bands of numbers in this solution's folder were taken either side of
that fix**, and nothing else about the policy changed between them. The folder's
twenty-table band, which is where the port was checked, was measured under the
first version of the rule. The held-out queue below was walked under the
corrected one. Reading them side by side is how the rest of this page gets its
evidence, and it is also the reason the two look so unlike each other.

## What the held-out queue measured

Fifty tables are offered in order from table ten thousand, with fifteen minutes
of arm time for the whole queue, and the queue is walked three times because the
policy draws its answer from fresh noise at every ask. The geometry reference's
column is beside it as a scale. Every figure is the median of the three walks
with the three values beside it.

| fifty tables offered from 10,000 | the geometry reference | **this, with the clearance check** | this, without it |
|---|---|---|---|
| Tables attempted | 26 | 11 (11, 11, 11) | 15 |
| Glasses on those tables | 102 | 40 (40, 40, 40) | 57 |
| Tables separated, nothing broken | **10** | 0 (1, 0, 0) | **0** |
| Tables failed by a topple | **0** | **0** | 14 |
| Tables left unfinished | 16 | 11 (10, 11, 11) | 1 |
| Glasses pickable at the end | 64 | 16 (18, 16, 16) | 1 |
| Of those, had room already | 39 | 16 (16, 16, 16) | 2 |
| Glasses it gave room to | +25 | 0 (+2, 0, 0) | **−1** |
| Share of glasses pickable | **0.627** | 0.400 (0.450, 0.400, 0.400) | 0.018 |
| Glasses broken | **0** | **0** | 20 |
| It declared a table finished | 24 of 26 | 10 of 11 (10, 10, 9) | 0 of 15 |
| Arm seconds for a table it separated | 43.6 | 122.8, once | nothing separated |
| Thinking an answer | 15 ms | 279 ms | 776 ms |

Read the two right-hand columns against each other, because the weights are the
same weights and nothing was retrained between them.

**Without the check, forty of its forty-three tables ended with a glass on the
floor.** With it, none do. The glasses were not being broken by badly aimed
pushes: they were being swept by a hand travelling at the height of their rims,
which the next section but one explains, and the check raises such a path before
the arm moves.

**Its share goes from 0.018 to 0.400, and almost all of that is glasses it never
touched.** That sounds like a contradiction and is not. A table where a glass
went over earns nothing at all — not even for the glasses that already had room
when the arm arrived — because if a lost table still paid out, a risky shove
would be close to free and a method could gamble its way up the card. So when no
table is lost, the glasses that arrived with room are counted, and the row above
says what the solution added to them in two walks of three: nothing.

**One walk of the three freed two glasses and separated one table**, which is
why the separated row reads 0 with a spread of 0 to 1 rather than a flat zero. A
model that has never seen this cell will occasionally shove a crowded glass in a
direction that happens to help. Three walks is the smallest number that can tell
that apart from a solution that does it on purpose, and the other two walks left
every table as they found it.

**It reaches eleven tables where it used to reach fifteen.** A raised answer
still costs the arm the move it asked for, and the stopping rule asks for sixteen
answers in a row that could not touch a glass before it takes the policy at its
word, so a table now costs about nineteen answers and eighty arm seconds. Before
the check, tables ended sooner because a glass fell.

**On the tables below the held-out line it does break glasses, up to four in a
run**, and that is in the solution's own folder rather than here because those
tables are not the score. The reason is worth knowing: the clearance arithmetic
now carries a shove on until the glass it names has room, once the solution has
watched that glass move, so a few of this policy's answers become real pushes.
A real push from a model that is not aiming at anything sometimes topples
something. The held-out walks happened not to contain one; the building tables
did.

It is worth noting what is *not* on that list. It is not slow at the arm in the
old sense: it spends the whole fifteen minutes, like every other solution. Under
the earliest version of the stopping rule a table cost it about seven arm seconds
and it would have reached the whole queue with most of the budget unspent. That
is a ten-fold change in what a table costs, and the policy did not change at all.
The rules that read it did.

## What it takes for this policy to say it is finished

This is the plainest fact on the card, and the explanation is short.

Three numbers describe one of this policy's answers: how low it comes, how far
across the table it travels, and how far apart its waypoints are. Measured over
nearly a thousand answers, the middle answer comes down to about 146 mm. The
hand hangs about seventy millimetres below that, so the lower edge of the hand on
the middle answer is at about 76 mm — within a millimetre or two of the height
the jaw pushes at, and below the top of every glass on the table.

So **as the policy draws them, almost every answer is a push.** That is not a
quirk of the shared rule; it is the rule being right. A hand crossing the table
at that height really is in among the glasses, and it really would move one. On
the walk without the clearance check the counter of quiet answers was therefore
reset by nearly every answer and never reached its threshold, the policy was
never taken to have declared anything, and a table ended only when a glass went
over or the clock stopped. The evidence that this was the mechanism, rather than
tables merely ending early, is the one table in that walk which the clock
stopped: the policy was asked 369 times on it and never produced three answers in
a row that the rule would call quiet.

**With the clearance check the same answers are raised before the arm moves, and
a raised answer touches nothing.** So the counter now runs, sixteen in a row are
reached on almost every table, and the policy is recorded as saying the table
needs nothing more. It is saying something true. What it proposed could not be
carried out, so it proposed nothing.

Three readings of one unchanged behaviour, then: under the first rule it looked
busy and quit after three answers; under the corrected rule it looked busy and
broke twenty glasses; with its own answers checked it is plainly idle. **Only
the last of those is a fair description of the policy**, which is the argument for
the check being part of a solution rather than part of the examiner.

## Why the answers came down, which is not the camera

Two things about this solution's input changed between problem 3 and problem 4,
and the point of this section is to keep them apart.

**The first change is the picture, and it is what problem 4 is about.** Problem
3 showed the model a rendered view from a camera above the table. Problem 4
shows it the view from the camera on the wrist.

**The second change is the jaw pose, and it is a side effect.** Along with the
picture, this kind of model is told where its own hand is. In problem 3 the
bench parked the jaw above travel height between actions, so the pose the model
was told about clipped to the very top of the range the join can express, on
every ask of every table. Problem 4's contract hands over the last waypoint of
the last path actually carried out, which is a real pose the join has already
clipped into its own box. So from the second answer of every table onwards, this
model is told a pose inside its range instead of one pinned at the ceiling.
Nobody chose that for this solution's benefit; it follows from problem 4 having
no separate "look" action.

The folder's sensitivity check is what separates them. It runs the same twenty
tables with the **wrist picture** and problem 3's **parked jaw pose**, so the
picture is the only thing that differs from problem 3.

| middle answer | problem 3: top view, parked pose | problem 4: wrist view, parked pose | problem 4: wrist view, real pose |
|---|---|---|---|
| How low the answer comes | 217 mm | 236 mm | **145 mm** |
| How far it travels across the table | 868 mm | 732 mm | 583 mm |
| Answers reaching the pushing height | — | 0 of 58 | 8.4% of 202 |

Read it from right to left. The seventy millimetres the answers dropped between
problem 3 and problem 4 is **entirely the pose**, and the picture contributed
none of it. With the wrist picture and the old parked pose, the answers come back
no lower than problem 3's, and not one of fifty-eight of them reached the height
a push happens at.

Two cautions about that table, which the folder also gives. The left column is
problem 3's own held-out tables under problem 3's draw, so comparing it with the
middle column crosses the tables as well as the picture; 236 against 217 should
be read as "no lower", not as "eighteen millimetres higher". The comparison
between the middle and the right column is the clean one: the same tables, the
same draw, the same code, one switch.

**So the honest answer to the question this solution was ported to ask is no.**
A camera where the model is used to having one did not move its answers towards
this table by a single millimetre. What moved them was being told a hand pose
near the table, and that is a property of problem 4's bookkeeping rather than of
the wrist camera.

The underlying reason is one sentence of this kind of model's design: it emits
**absolute targets near the state it is given**. Tell it the hand is at the
ceiling and it answers near the ceiling. Tell it the hand is near the table and
it answers near the table. Nothing in that depends on what the picture shows, so
nothing in the picture had a chance to change it. The gap between this model and
this cell was never the camera position. It is that the model has no idea what
is in the picture it is being shown.

## Why closer to home ground turned out worse

Put the last two sections together and the result stops being a surprise.

The policy proposes a long path at the height of the glasses. The middle answer
travels 583 mm across a zone that is 320 mm by 360 mm, so one answer crosses the
whole of the glass zone and comes back. The hand is 139 mm across its fingers.
Dragging that hand across the whole zone at the height where glasses stand means
sweeping everything in its way, and a glass swept sideways near the top of its
body goes over rather than sliding, because the push is far above the point where
a glass can be shoved safely.

And the policy never stops, so it does this over and over. A table ends when a
glass falls. On these tables, one falls.

**That is why being nearer the model's home ground made it worse.** In problem 3
the same policy was wrong in a harmless direction: it waved the hand through
empty air, so its answers cost arm time and changed nothing. In problem 4 it is
wrong by about the same amount, in the same way, but the error now lands on the
table. **A path that reaches the glasses without aiming at them is more
destructive than a path that never reaches them at all**, and nothing about
moving a model's input closer to its training distribution promises that its
remaining error will fall somewhere harmless.

The twenty-table band in the folder, taken under the first stopping rule, is the
measurement that makes this concrete rather than rhetorical. There the same
policy, with the same lowered answers, broke two glasses out of eighty-four,
because it was allowed to leave each table after three answers. Given the whole
clock, it breaks twenty out of fifty-seven. The destructiveness was always
there; what the earlier rule did was let it leave before the damage was done.

## Why the cell's interlock cannot save it

The cell keeps one real judgement of its own: it will not drive the hand into a
glass that the physics says would tip rather than slide. It is a safety
interlock, it works from information anybody could compute, and it was itself
corrected for the same seventy-millimetre fault described above, so it now
measures from where the hand really is.

It still refused almost nothing. Over the three walks it fired ten times, once,
and 251 times, and the 251 were nearly all on a single table. Twenty glasses
went over on paths it allowed.

That is not a second bug. It is the limit of what the interlock was ever asked.
The rule it applies answers one question: *would a push at the hand's own
working height slide this glass, or tip it?* And the draw deliberately
guarantees that every crowded glass on every table is one that slides at that
height, so there is almost never a glass on the table for the interlock to
refuse. A path that meets a glass seventy millimetres higher up is a different
question with a different answer — the same glass tips, because the hand is
pushing far above its foot — and the interlock has no question of that shape to
ask. The height test was corrected; the physics test behind it is still written
for one height.

The examiner is honest that this would happen: the interlock is one test at one
moment and was never a promise that nothing can fall over. It is worth recording
anyway, because a reader looking at twenty broken glasses and a safety interlock
in the same cell deserves to know why the second did not stop the first.

**That gap is exactly what this solution now closes from its own side.** The
cell's interlock asks about one glass at one height. `keeping_clear`, which the
solution runs over its own answer, asks a different question: is this path either
a move at travel height, where nothing on the table can be reached, or a push at
one named glass, carried out at the height a push works at? A path at the height
of the glasses' rims is neither, so it is raised. The cell is unchanged and
refuses exactly what it refused before; what changed is that the solution no
longer hands it a path that nobody can account for. Six hundred and twenty-two of
the 624 answers it gave over the three walks were raised, and the reasons have
spread out since the first walk: 341 of them because the path comes down at no
glass in particular, 140 because it rides at the height of the glasses' rims, 83
because nothing has yet tested whether the glass it names would slide, and 53
because the hand would meet a glass it is not aimed at.

## What the saved numbers do not settle

Three things in this write-up are weaker than the rest, and it is better to name
them than to let them pass.

**The shape numbers come from the tuning band, not from the queue.** The 145 mm,
the 583 mm and the share of answers reaching the pushing height were all
measured on the twenty tuning tables under the first stopping rule, which let
the policy answer about three times a table. So they describe the opening
answers on a table. The held-out walk saved no shape numbers at all, so whether
the middle answer stays that low over the twenty-odd answers a table it now
gives is **not measured**. The measurement that settles it costs no arm time,
because it is a tally on the laptop's side: save the same three numbers from a
walk of the queue.

**The picture and the pose were separated on one run, not three.** The
sensitivity check is a single walk of twenty tables with the pose pinned. Its
conclusion is strong because the gap it reports is large — about ninety
millimetres between the pinned and real pose, against a policy whose answers
vary by a few tens of millimetres — but a three-walk version of that check would
cost five minutes of laptop time and should be run before the conclusion is
quoted anywhere outside this folder.

**Nothing here measures what the model thinks the picture shows.** This page
says the model has no idea what is in the wrist view, and the evidence for that
is indirect: its answers do not change when the view does. A direct measurement
would be to ask it the same table from the same pose with the picture replaced
by an empty table, or by noise, and compare the answers. If they do not move,
the picture is not being used at all, and that is a much stronger statement than
this measurement can make.

## Where it sits beside the others

| fifty tables offered from 10,000 | 1 geometry | 2 ranked geometry | 4 world model | **5 as it downloads** |
|---|---|---|---|---|
| Tables attempted | 26 | 25 | **40** | 11 |
| Tables separated | 10 | 7 | **14** | **0** |
| Tables failed by a topple | **0** | **0** | 1 | **0** |
| Glasses it gave room to | +25 | +19 | **+39** | **0** |
| Share pickable | **0.627** | 0.582 | 0.598 | **0.400** |
| Glasses broken | **0** | **0** | 1 | **0** |
| Thinking an answer | 15 ms | 15 ms | **10 ms** | **279 ms** |

It is last on every line that measures work done, and it is now last without
being dangerous. Its share of 0.400 is almost exactly the share of glasses that
arrived with room: the column says, as plainly as a column can, that the
solution added nothing to the table in two walks of three and took nothing away
from it in any of them.

The nearest comparison is the [world model](04-a-world-model.md), which also
answers from a fitted model and which separates fourteen tables. The difference
between them is not that one is careful and the other is not — both now run the
same clearance check — it is that the world model is asked for a *push at a
named glass* and this one is asked for a path, and a path drawn by a model that
was never shown this cell's glasses is not aimed at anything.

**This result was expected to be poor and is still worth having**, for the
reason it was built: it is the baseline the same model fine-tuned on this cell
has to beat, and a baseline that is only interesting when it scores well is not
a baseline. What was not expected was the direction. Problem 3 ended with this
model harmless; problem 4's first measurement ended with it as the most
destructive solution on the card, having changed nothing about the model and only
one thing about what it is told. Its second measurement ends with it harmless
again — not because the model improved, but because the solution now declines to
carry out what it cannot account for.

## What to take from it

**Moving an input closer to a model's training distribution is not the same as
making the model competent.** The wrist camera did close a gap that was real —
it is the view a real robot carries, and problem 3's overhead view was a
convenience of the simulator — and closing it changed this model's answers by
nothing at all. What changed its answers was an accident of bookkeeping about
where the hand was said to be.

**A model that is wrong in a harmless direction is not safer than one that is
wrong in a harmful direction; it is luckier.** Problem 3 measured this policy
as nearly inert and read that as a domain gap. The same gap, with the hand told
a lower pose, puts twenty glasses on the floor. Nothing about the policy's
understanding improved or worsened between those two measurements.

**A stopping rule is part of the measurement, and a wrong one can hide a
hazard.** The first version of problem 4's rule let this policy leave each table
after three answers, and under it the same policy looked almost harmless. The
corrected rule does not punish it; it simply declines to call a hand that is
sweeping through the glasses "finished", and the damage then shows up where it
belongs.

**And a solution that cannot aim can still be made safe, which is worth having
even when it leaves the card unchanged.** Twenty broken glasses became none with
no retraining, because the arithmetic that says what a safe answer looks like in
this cell — travel high, or push one named glass at the height a push works at —
is available to every solution and costs nothing to apply. What it cannot do is
make a model competent: the same check applied to the
[fine-tuned model](06-smolvla-fine-tuned.md) and to the
[imitation policy](03-imitation-from-demonstrations.md) leaves each of them doing
whatever it had learned to do, minus the damage.

## Where to go next

- [The examiner](../the-examiner.md) — the tables, the arm's clock, the camera
  on the wrist, the one budget for the whole queue, the stopping rule, and every
  line on the card.
- [The problem](../problem.md) — what is on the table, what goes in, what comes
  out, and what "done" means here.
- [The same model in problem 3](../../03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md)
  — what kind of model it is, where its competence comes from, and the three
  places where borrowing hurts.
- [The world model](04-a-world-model.md) — the other solution in problem 4 that
  breaks glasses, and a very different reason for it.
- [The solution's own folder](../../../04-clear-the-table/05-smolvla-as-it-downloads/)
  — what is borrowed, the twenty-table band, the sensitivity check, and every
  per-table row quoted above.
- [Known gaps](../../known-gaps.md) — the limits this project knows it has.

---

← [Solution 4 — a world model](04-a-world-model.md) ·
[Problem 4 — clear the table](../problem.md) ·
[The examiner](../the-examiner.md)
