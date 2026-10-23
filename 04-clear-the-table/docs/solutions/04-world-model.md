# Solution 4 — the world model

The world model does not copy anyone. It learns what a push will do, and then it chooses a
push the way a person with a good model of the cell would: imagine many pushes, predict the
result of each, and make the best one. This page explains what it predicts, how it
searches, and why it is the best solution. By the end you will know why it also breaks the
fewest glasses.

## What it predicts

Given a table and a push, the model answers nine questions. The three that matter most are:
could MoveIt plan this push, would a glass tip, and **would the push work**, meaning it is
planned, nothing tips and a glass gets room. The others predict how far the glass moves,
how much the neighbours are disturbed, how long the arm takes and how much room is gained.

It learns from every one of the 12,609 pushes, including the failures. This is the key
difference from imitation: a push that tipped a glass teaches the model what to avoid, just
as a push that worked teaches what to do.

## Five models, not one

A search always picks the push the model is most hopeful about, and that is often a push
the model knows least about, so its prediction there is most likely to be wrong. To guard
against this, five copies of the network are trained, each on a different random sample of
the pushes. They agree where there is plenty of data and disagree where there is not, and
the search is charged for their disagreement.

## How it searches

1. **Draw candidate pushes from the geometry.** A candidate is a crowded glass, a direction
   and a distance where the hand fits between the glasses and the glass would end with room.
   Its six settings are drawn at random.
2. **Score every candidate.** The score is the chance the push works, minus the chance it is
   planned and tips a glass, minus a charge for the five models' disagreement, minus a small
   charge for arm time.
3. **Improve the best ones.** The best candidates are nudged a little in direction, distance
   and every setting, and scored again, twice.
4. **Push or stop.** It makes the best push. If no push scores above a small threshold, it
   says the table is finished.

So jobs 1 and 2 are one search. The settings are part of what the search varies, which is
how it learns to push tipping glasses low and straight glasses fast, as [the speed
table](../what-the-pushes-show.md#how-each-solution-sets-its-speed) shows.

## How good its predictions are

On 1,261 pushes it was not trained on, it tells pushes MoveIt can plan from ones it cannot
with an accuracy score of 0.92, pushes that tip from ones that do not with 0.97, and pushes
that work from ones that do not with 0.90. On this score, 1.0 is perfect and 0.5 is
guessing. Of the 20 pushes it rated most likely to work, 8 did, where only about one push
in 34 works at random.

## How much data it needs

| Pushes it learned from | Gain on the held-out tables |
|---|---|
| 1,927 | +0: no push ever looked worth making |
| 4,794 | +9 |
| 8,837 | +8 |
| 12,609 | +9 |

It needs a few thousand pushes before it acts at all. After that, more of the same kind of
data does not help much. These gains were measured before the solutions chose how much to
look. The model trained on all 12,609 pushes, measured again now, gains 6, and a difference
of that size is within the noise of one run.

## How it does

It gains 6 glasses, breaks 2, and says "finished" on 48 of the 50 tables, using under 5 arm
minutes (see the [results](../README.md#results)). The two geometry solutions gain more,
+11 and +9, but they break 18 and 16 glasses, because nothing in them knows which glasses tip.
Of the solutions that break almost nothing, the world model gains the most. However, it finds
only about a quarter of what the ceiling finds. A wider
search did not help: three times as many candidates gave +5 against +6 on the training
tables. More gain would need data chosen where the five models disagree, or a search that
plans two pushes ahead.

## Where the code is

Its code and weights are in [`04-world-model/`](../../04-world-model/README.md), together with the [safety check](safety-check.md), because the check is this same model judging another solution's push.
