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
Problem 4 racks nothing, has no push budget, and keeps the tipping refusal in
the cell itself. `as_downloaded.py` is the replacement and is the only new
thinking in this folder.

## How it says it is done

Problem 4 asks every solution to declare a table finished, and that is a
sentence this policy cannot utter: it answers with a path for the jaw and has
no spare output meaning "nothing here needs moving". `bench/stopping.py` is the
shared answer, and this solution uses it unchanged — a run of three answers
that do not come down to the height a push happens at is taken as the policy
saying it sees nothing to do. The third such answer is the declaration and is
not carried out, because following it would spend arm seconds to change
nothing.

In practice that is what ends almost every table, after **three answers**.

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
| Tables separated, nothing broken | **5** | 2 | 1 | 0 |
| Glasses broken | **0** | 3 | 0 | 2 |
| Glasses pickable at the end | **47** of 84 (0.56) | 33 (0.39) | 35 (0.42) | 32 (0.38) |
| Of which it made pickable | **+14** | +4 | +2 | +1 |
| Arm seconds a table | 42.6 | **6.4** | **8.0** | **6.8** |
| Of that, on paths that never came down | 46% | 93% | 84% | 86% |
| Said done while the table was still crowded | 15 of 20 | 16 of 20 | 19 of 20 | 19 of 20 |
| Tables stopped by the clock | 0 | 0 | 0 | 0 |
| Answers a table | 37 | 3.2 | 3.6 | 3.3 |
| Thinking per answer | **16 ms** | 1.33 s | 1.30 s | 1.29 s |
| Paths the cell's interlock refused | 0 | 5 | 6 | 6 |

**It is six times faster at the arm, eighty times slower at the laptop, and it
frees a seventh as many glasses.** The arm time is low for one reason only:
it quits after three answers, so a table costs three chunks and is handed back
very nearly as it was found. Against problem 4's queue budget of 900 arm
seconds it would reach all twenty tables and have most of the budget left, but
"how far down the list it got" is not a reading worth having when the tables it
reached were left crowded.

**It breaks glasses, and that is where the gain goes.** Two of the three runs
lost glasses, and a table that loses one pays nothing at all, which is why the
pickable share moves below the share it started with on run 2. Solution 1 broke
none.

**One number in this table should be read narrowly**, and it is the one
labelled "never came down". It is the share of arm seconds spent on paths whose
lowest waypoint stayed above the height a push happens at. It is *not* the
share spent harmlessly, and the section after next says why.

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
| Answers that reach the pushing height | — | 0 of 58 | 8.4% of 202 |

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
this table. 146 mm is still twice the 75 mm the jaw pushes at, and fewer than
one answer in ten comes down to pushing height at all. What the model proposes
is still a sweep through the air across most of the glass zone — 583 mm of
travel, where the zone is 320 by 360 mm, so one chunk crosses the whole of it
and comes back.

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
