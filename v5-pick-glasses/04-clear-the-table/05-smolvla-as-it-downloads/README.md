# Problem 4 — a borrowed foundation model, run exactly as it downloads

`lerobot/smolvla_base`, with nothing trained, nothing fitted and nothing tuned.
The weights arrive on the first run and are used as they come. The question it
answers is what a general model already knows about this cell before anybody
teaches it anything.

This is [problem 3's solution 5](../../03-push-glasses-apart/05-smolvla-as-it-downloads/)
ported to problem 4's contract. The model and the whole join between what it
emits and this cell's jaw are **imported, not copied**.

## The prediction, written down before the run

Problem 4 exists partly because an overhead camera is a convenience of the
simulator. For this solution that change is not a handicap but the opposite.
The borrowed model was pretrained on real robots, and a real robot almost
always carries its camera on the wrist. Problem 3 handed it a picture from a
camera bolted above the table, which is a view it would hardly have met in
training, and its answers came back high: the median chunk's lowest point was
**217 mm** above a table whose glasses stand on it, so the jaw swept through
the air above them rather than at them.

Problem 4 gives it the wrist view it is used to. So its input here is **closer
to its home ground than problem 3's was**, and the prediction was that this
narrows the gap between what the model expects and what this cell gives it, and
that its answers should therefore look more like pushes than they did in
problem 3.

**The prediction did not hold.** The answers did come down — a long way — but
the wrist view is not what brought them down, and the section below separates
the two. Measured with the picture changed and nothing else, the chunks come
back **no lower than problem 3's, and if anything slightly higher**.

## What is borrowed and what is new

| | |
|---|---|
| `joining.py` in problem 3's solution 5 | **borrowed, unchanged.** How six of somebody else's joint readings become jaw waypoints, and how the jaw's pose becomes the model's state. Every number in it is read off the checkpoint or off the cell. |
| `policy.py` in problem 3's solution 5 | **borrowed, unchanged.** Loading the weights and asking them. |
| `bench/stopping.py` | **borrowed.** How a trained policy says it has finished, when it has no words for it. This solution invents no second rule. |
| `bench/keeping_clear.py` | **borrowed.** The clearance check every solution in this problem runs over its own answer. Added after the first walk of the held-out queue, which broke twenty glasses. |
| `bench/wrist.py`, through the contract's `Look` | **borrowed.** The picture comes from the cell. Nothing here builds a camera. |
| `borrowed.py` | **new.** Loads the two problem 3 files under the plain names they import each other by. |
| `as_downloaded.py` | **new.** The model sat in problem 4's conversation, and the shape of its answers. |
| `measure.py` | **new.** Twenty tables, three times over. |

**The join is held still on purpose.** `joining.py` maps the model's
normalised output onto the frame of problem 3's overhead picture, and problem 4
does not re-choose that box even though the overhead picture is gone. If it
did, a difference between the two problems would be a difference between two
joins and would say nothing at all about the wrist camera.

**Problem 3's `clear.py` is not borrowed, because there is nothing left of it
to borrow.** Its loop racks every glass that has room, counts pushes against a
push budget, and refuses a path that would reach a glass that would tip.
Problem 4 racks nothing and has no push budget. `as_downloaded.py` is the
replacement and is the only new thinking in this folder.

**One thing problem 3's loop did is back, for a measured reason.** It checked a
path against the glasses before letting it be carried out, and the first version
of this solution did not, because problem 4's cell keeps a tipping interlock of
its own. That interlock is narrow on purpose — it refuses only a path into a
glass the public rule says would topple rather than slide — and the first walk
of the held-out queue broke twenty glasses inside it. Not by aiming badly: by
travelling. The fingers hang seventy millimetres below the number a waypoint
carries, so a path that looks high in its own numbers drags the hand through the
tops of the glasses, and this model had learned to travel at exactly that
height. So every answer now goes through `keeping_clear`, which raises a path
that cannot be shown to reach only the glass it names. The model still chooses
every answer; what it no longer does is carry one out that nobody can account
for.

## How it says it is done

Problem 4 asks every solution to declare a table finished, and that is a
sentence this policy cannot utter: it answers with a path for the jaw and has
no spare output meaning "nothing here needs moving". `bench/stopping.py` is the
shared answer, and this solution uses it unchanged — a run of answers that could
not touch any glass is taken as the policy saying it sees nothing to do, and the
count that is enough is the bench's own, measured from the teacher's longest
quiet spell. The answer that completes the run is the declaration and is not
carried out, because following it would spend arm seconds to change nothing.

In practice that is what ends every table now, after **sixteen answers**. Before
the clearance check went in, this solution never gave even three quiet answers in
a row and declared no table finished at all: its paths came down low, so every
one of them counted as the policy acting. Now they are raised, and a raised path
touches nothing, so the rule reads them for what they are.

## What it costs and achieves — twenty tables, seeds 0 to 19, three runs

Tables **below** `TEST_SEEDS`; the held-out tables are scored once and not by a
run made while building. Three runs, because the policy denoises from fresh
noise at every ask, so the same table asked twice gives two different answers
and one run is not a measurement. The three runs are the three columns.

Solution 1's column was **re-measured on the same draw**, not copied from its
own README. `bench/tables.py` was changed while this solution was being built —
three to five glasses now, two or three of them crowded — and the numbers
committed in [`01-one-fixed-nudge/calibration.json`](../01-one-fixed-nudge/calibration.json)
are from the draw before that. Putting them here would compare the draws.

| twenty tables, 84 glasses | solution 1 | run 0 | run 1 | run 2 |
|---|---|---|---|---|
| Tables separated, nothing broken | **5** | 0 | 0 | 0 |
| Glasses broken | **0** | **0** | 2 | 4 |
| Glasses pickable at the end | **47** of 84 (0.56) | 31 (0.37) | 31 (0.37) | 26 (0.31) |
| Of which it made pickable | **+14** | −2 | 0 | 0 |
| Arm seconds a table | **42.6** | 91.9 | 72.1 | 76.5 |
| Of that, on paths that could not touch a glass | 46% | 94% | 99% | 94% |
| Said done while the table was still crowded | 15 of 20 | 20 of 20 | 19 of 20 | 16 of 20 |
| Tables stopped by the clock | 0 | 0 | 0 | 0 |
| Answers a table | 37 | 22 | 17 | 18 |
| Thinking per answer | **16 ms** | 0.28 s | 0.28 s | 0.28 s |
| Paths the cell's interlock refused | 0 | **0** | **0** | 1 |

**It frees nothing, and it is no longer harmless on these tables.** No table is
separated in any of the three runs and no glass is given room it did not start
with, which is the result this solution exists to produce: a model that has
never seen this cell does not clear a table in it. What has changed since this
page was first written is the second row. The clearance arithmetic the solution
runs over its own answers used only to raise a path that could not account for
itself; it now also carries a shove on until the glass it names has room, once
the solution has watched that glass move. So a few of this policy's answers are
now carried out as real pushes, and a real push by a model that is not aiming at
anything sometimes puts a glass over: none in the first run, two in the second,
four in the third.

**Those three runs are not an average, and reporting them apart matters.** The
policy denoises from fresh noise at every ask, so the three columns are three
draws of the same solution, and the glasses broken go 0, 2, 4 across them. A
single run of this solution says very little, which is why three are run and all
three are printed.

**This is still a different result from the one this page used to report.**
Before any clearance arithmetic, the same weights on the same twenty tables
broke three glasses in one run and two in another, and spent six to eight arm
seconds a table because they quit after three answers. A table now costs
seventy to ninety seconds, because seventeen to twenty-two answers are given
before the stopping rule takes the policy at its word, and most of those answers
are raised to travel height where they touch nothing.

**Read the arm-time row beside the glasses row.** Eighty seconds a table for
nothing is worse value than forty-three seconds a table for five separated
tables, so the geometry reference is better by every reading here. What this
column is for is the comparison with [solution
6](../06-smolvla-fine-tuned/README.md), which is the same weights fine-tuned on
this cell's own demonstrations.

## The shape of its answers, which is the heart of it

Three numbers describe one answer: how low the chunk comes, how far across the
table it travels, and how far apart its waypoints are — which in this cell is
the speed being asked for, because the bench eats waypoints at a fixed rate.

The middle column is the sensitivity check, `make pinned`, and it is what makes
the result readable. It runs the same twenty tables with the **wrist picture**
and problem 3's **parked jaw pose** as the state, so the only thing that
differs from problem 3 is the picture.

| median over all answers | problem 3: top view, pinned state | problem 4: wrist view, pinned state | problem 4: wrist view, real state |
|---|---|---|---|
| Lowest point of a chunk | 217 mm | **236 mm** | **146 mm** |
| Travel across the table | 868 mm | 732 mm | 583 mm |
| Step between waypoints | 14.6 mm | 11.4 mm | 10.0 mm |
| Answers that reach the pushing height | — | 0 of 58 | 15.5% of 1,119 |

**The wrist view did not help. The state did.** Reading the columns right to
left: the 72 mm the answers dropped between problem 3 and problem 4 is entirely
the state input, and the picture contributed none of it. Problem 3 measured
that state effect in advance and put it at 60 to 70 mm, which is what this
found: its bench parked the jaw above travel height between actions, so the
reading clipped to the top of its range at every ask on every table, and
SmolVLA emits absolute targets near the state it is given. Problem 4's
`Look.jaw` is the last waypoint of the last path carried out, which the join
has already clipped into the box it can express, so from the second answer on
the model is told a real pose inside its range. **That is a side effect of
problem 4's contract, not a property of the wrist camera.**

Two cautions on reading the table. The left column is problem 3's own fifty
held-out tables under problem 3's draw, so left-against-middle crosses the
tables as well as the picture; 236 against 217 is best read as "no lower", not
as "18 mm higher". The middle-against-right comparison is clean: same tables,
same draw, same code, one switch.

**So the honest answer to the question this solution was ported to ask is no.**
A camera where the model is used to having one did not move its answers toward
this table. 146 mm is still twice the 75 mm the jaw pushes at, and about one
answer in six comes down to pushing height at all. What the model proposes
is still a sweep through the air across most of the glass zone — 583 mm of
travel, where the zone is 320 by 360 mm, so one chunk crosses the whole of it
and comes back. About one answer in six does come down as far as the pushing
height, and the clearance arithmetic finds that most of those come down at no
glass in particular.

## Two things about problem 4 this solution found

**`bench/stopping.py` reads "quiet" as "harmless", and in this cell it is
not.** Its docstring says an answer that never descends to the pushing height
"cannot move a glass whatever else it does". That is false here, and the
measurement is plain about it: the pinned run recorded **no answer at all**
reaching the pushing height and still put a glass on the floor.

The arithmetic is the jaw's own. A waypoint's `z` is the middle of the jaw, and
the hand reaches `JAW_HALF_HEIGHT`, 69.5 mm, below that. Glasses on these
twenty tables stand 97 to 224 mm tall. So the hand's lower edge is at table
level on a path 145 mm up, and a path has to be above about **294 mm** — all
but travel height itself — before it is clear of the tallest glass drawn. The
median answer at 146 mm is therefore sweeping the top of every glass on the
table while the stopping rule records it as the policy saying it sees nothing
to do.

This does not make the rule unfair, and it does not change the score: the
scorecard looks at the table rather than at the policy, so the broken glasses
are counted where they belong. It makes the rule's **stated reason** wrong, and
it means "quiet answers" must not be read anywhere as "answers that touched
nothing". The fix, if the rule is revisited, is one term: compare
`z - JAW_HALF_HEIGHT` against a glass's height rather than `z` against the
pushing height.

**The cell's tipping interlock under-refuses for the same reason.**
`open_run.hand_meets` skips a leg of a path when `min(start.z, end.z)` is above
the glass's height, and its comment gives the reason as "a leg is only in the
way while it is low enough to reach the glass at all". With `z` at the middle
of the jaw, low enough to reach means `z - JAW_HALF_HEIGHT <= glass.height`,
so every leg in the 69.5 mm band just above a glass is skipped although the
hand would go through it. That is the band this solution spends most of its
time in, which is why the interlock fired five or six times a run and glasses
still went over on paths it passed. It is a bug in a safety check, not in the
score.

Both are in `bench/`, which is not this folder's to change. They are reported
here and in the hand-back.

## What it scores — the held-out queue, fifty tables offered from 10,000

Everything above was measured on tables below `TEST_SEEDS`. **This is the
score**: fifty tables offered in order from table 10,000, fifteen arm minutes
for the **whole queue**, walked three times through the bench's own judging.
Medians of the three walks, with the three values in brackets, the geometry
reference's walk of the same queue as a scale, and this solution's own first
walk — before it ran the clearance check over its answers — as the thing the
change is measured against.

| | geometry reference | **this, as it downloads** | before the clearance check |
|---|---|---|---|
| Tables attempted | 26 | 11 (11, 11, 11) | 15 |
| Glasses on those tables | 102 | 40 (40, 40, 40) | 57 |
| Tables separated, nothing broken | **10** | 0 (1, 0, 0) | **0** |
| Tables failed by a topple | **0** | **0** | 14 |
| Tables left unfinished | 16 | 11 (10, 11, 11) | 1 |
| Glasses pickable at the end | 64 | 16 (18, 16, 16) | 1 |
| Of those, had room already | 39 | 16 (16, 16, 16) | 2 |
| Glasses it gave room to | +25 | **0** (+2, 0, 0) | −1 |
| Pickable share | **0.627** | 0.400 (0.450, 0.400, 0.400) | 0.018 |
| Glasses broken | **0** | **0** | 20 |
| It said a table was finished | 24 of 26 | 10 of 11 (10, 10, 9) | 0 of 15 |
| Arm seconds for a table it separated | 43.6 | 122.8, in the one walk that separated one | nothing separated |
| Answers a table | 31 | 19 (20, 18, 19) | 22 |
| Thinking an answer | 15 ms | 279 ms | 776 ms |
| Paths the cell's interlock refused | 0 | **0** | 10 |

**Two rows carry the whole change: twenty glasses broken became none, and a
share of 0.018 became 0.400.** Very little of that is the model doing anything
better. The share rises because a table that loses a glass counts for nothing at
either end, so once no table is lost the glasses that already had room are
counted — and "the glasses that already had room" is almost the whole of this
column, because the row above it says the solution gave room to none in two
walks of three.

**One walk of the three separated a table, and it is worth neither hiding nor
celebrating.** In the first walk two glasses were given room they did not start
with and one table came out clean, which is why the separated row reads 0 with a
spread of 0 to 1. A borrowed model that has never seen this cell will
occasionally shove a crowded glass the right way, and three walks is exactly the
number needed to tell that apart from a method that does it on purpose. The
other two walks freed nothing.

**It breaks nothing here and breaks up to four glasses on the tables below the
line.** The two runs disagree, and both are reported rather than averaged. The
tables below the line are given four arm minutes each, so the policy gives
seventeen to twenty-two answers on each of twenty tables; the held-out queue
gives the whole quarter of an hour to all fifty, so a walk reaches eleven tables
and gives about nineteen answers on each. More answers mean more chances for one
of the few that survive the clearance check to be a shove that topples
something.

**Why it reaches fewer tables than it did.** Its answers are mostly raised, a
raised answer touches nothing, and the stopping rule asks for sixteen answers in
a row that could not touch a glass before it takes a policy at its word. So a
table costs about nineteen answers and the crossings that go with them, where
before the policy was stopped by a falling glass after a handful of them. The
arm time went up and the damage went to zero, and both come from the same fact:
an answer that cannot be shown to be safe is still carried out as a move to a new
viewpoint, and a move costs arm seconds.

**The thinking time fell from 776 ms to 279 ms, and that is not this solution
either.** The first walk ran on a laptop that was fitting other solutions at the
same time. This one did not.

**It now says a table is finished, and the reason is worth reading carefully.**
Its median answer bottoms out at 146 mm; the hand hangs `JAW_HALF_HEIGHT` below
that, so the fingers ride at about 76 mm, below the top of every glass on the
table and within a millimetre or two of the pushing height. Before the clearance
check, such a path was carried out as drawn, the stopping rule rightly counted it
as the policy acting, and the quiet counter never reached its threshold. Now the
same path is raised to travel height first, so it really does touch nothing, and
sixteen of them in a row really are the policy saying it sees nothing to do. The
rule has not changed. What it is reading has.

**The prediction this solution was ported to test is answered, and the answer is
no.** Giving the model the wrist camera it was pretrained with did not make it
better at this task; it made it worse, and the sensitivity check says which half
of the change did it. The wrist picture moved its answers not at all: with the
picture changed and the pose pinned to problem 3's parked pose, the chunks come
back at 236 mm, no lower than problem 3's 217. The ninety-millimetre drop to
146 mm is the **state**, because this model emits absolute targets near the pose
it is told about, and problem 4's `Look.jaw` is a real pose inside the join's box
where problem 3's parked pose clipped to the ceiling. So it now reaches the
glasses without aiming at them, which on its first walk was more destructive than
never arriving at all, and which the clearance check now turns into an answer
that mostly changes nothing.

**What the clearance check tells us about its answers, counted by reason.** Over
the three walks, 622 of its 624 answers were raised to travel height, and the
reasons are no longer all one reason:

| why an answer could not account for itself | over three walks |
| --- | --- |
| it comes down without reaching the glass it names | 341 |
| it travels across the table at the height of the glasses' rims | 140 |
| the glass it names may tip rather than slide, and nothing has tested it | 83 |
| the hand would meet a glass it is not aimed at | 53 |
| the glass it names would tip rather than slide | 3 |
| it would drive the glass it names into another glass | 2 |

The commonest reason has moved, and the move is informative. On the first walk
every answer was raised for riding at the height of the glasses' rims, because
every answer was a sweep at that height. Now the commonest reason is that the
path comes down somewhere that is not the glass it is nearest to, which is the
same failure seen closer up: the model is coming down to roughly the right
height and is not coming down at a glass.

**A note about the interlock, since it refused nothing.** `plan.slides` answers
whether a push **at the jaw's own working height** slides a glass, and the draw
guarantees that every crowded glass does, so there is almost never a glass for
the interlock to refuse. A path that meets a glass seventy millimetres higher up
tips that glass, and the interlock has no question of that shape to ask. That is
why it refused almost nothing while twenty glasses went over on paths it passed,
and it is exactly the gap `keeping_clear` fills from the solution's side.

**What is not settled.** The pinned check is one walk of twenty tables, not
three. And nothing here measures whether the model uses the picture at all — the
direct test is to ask it the same table from the same pose with the picture
replaced by an empty table or by noise, and see whether the answers move.

## Running it

```
pixi run python 05-smolvla-as-it-downloads/measure.py --tables 20 --runs 3 \
    --save 05-smolvla-as-it-downloads/measurement.json
pixi run python 05-smolvla-as-it-downloads/measure.py --tables 20 --runs 1 --pinned \
    --save 05-smolvla-as-it-downloads/pinned.json
pixi run pytest -q 05-smolvla-as-it-downloads
```

`make measure` and `make pinned` are the same two. The first run downloads
about 2 GB of weights and then reads them from the cache. The whole
measurement is about five minutes of laptop time on this machine, nearly all of
it forward passes.

`measure.py` refuses any seed from `TEST_SEEDS` up. No test here loads a model:
a test that needs two gigabytes off the internet is not a test, and what is
worth testing is the wiring either side of the weights, not the weights.
