# Problem 4 — clear the table

A table holds three to five glasses, and some of them stand too close together for the
gripper to close round one. A UR5e arm, with a camera on its wrist, has to push the glasses
apart until every glass has room to be picked up, without tipping any. Then it has to say
for itself that it has finished. This page gives the whole picture and every result in one
place. The other pages each explain one part.

## The main idea: a learned model decides, MoveIt moves

A solution never writes a joint angle. The work is split into four jobs, and only the
middle two are what the solutions compete on.

| | Job | Who does it | Page |
|---|---|---|---|
| 0 | Draw a box round every glass, so MoveIt can plan round it | a network that reads the wrist picture | [the box model](the-box-model.md) |
| 1 | Choose which glass to push, and where it should go | the solution | [the solutions](#the-solutions) |
| 2 | Choose the settings handed to MoveIt, so the glass does not tip | the solution | [the solutions](#the-solutions) |
| 3 | Move the arm | MoveIt 2 | [the arm and MoveIt](the-arm-and-moveit.md) |

Jobs 1 and 2 are one answer. On each turn a solution chooses one **push**: this glass,
this direction, this distance, and six settings such as how high and how fast the hand
moves. Or it decides that the table is **finished**.

## One turn

A solution is handed the arm, with its wrist camera, and a clock, and it works through the
table itself, one turn at a time. On a turn it looks, and the box model turns each picture
into boxes. Then the solution chooses a push, or says "finished". MoveIt plans the push as
four motions, and the arm carries them out in the MuJoCo physics engine. Then the next turn
starts.

How much to look is each solution's own choice. At the start of a table every solution looks
from both viewing places, because a glass hidden behind another glass is missing from one
picture. After a push, a solution that reads only the boxes goes to the nearer place first,
and goes on to the other only when the first picture shows fewer glasses than before. SmolVLA
reads the pictures themselves, so it takes both on every turn. A push that MoveIt refuses
moves nothing, so after one, no solution looks again.

![The same table from the two viewing places, with the boxes the box model drew](../images/full-arm-two-views-and-boxes.png)

## The solutions

Every learned solution learns from the same thing: pushes that the arm really made, and
what happened to each one. [What the pushes show](what-the-pushes-show.md) describes
those pushes.

| # | Solution | How it chooses a push | Page |
|---|---|---|---|
| 1–2 | Geometry reference | Fixed rules and fixed settings; nothing is learned | [page](solutions/01-02-geometry-reference.md) |
| 3 | Imitation | Copies pushes that worked | [page](solutions/03-imitation.md) |
| 4 | World model | Learns what a push will do, then searches for the best push | [page](solutions/04-world-model.md) |
| 5 | Reinforcement learning | Learns by trying pushes and being scored | [page](solutions/05-reinforcement-learning.md) |
| 6 | SmolVLA | A large vision-language-action model with a small fitted correction | [page](solutions/06-smolvla-fine-tuned.md) |

Two more things appear in the results. The [safety check](solutions/safety-check.md) lets
the world model reject another solution's push when it expects that push to tip a glass.
**The ceiling** is a search that tries 30 pushes in the physics before every move and makes
the best one. A real arm cannot try a push before making it, so the ceiling is not a
solution. It shows how much could be gained on these tables.

## Results

Each row walked the same 50 held-out tables, with the same 15 arm minutes for the whole
list. [The problem](problem.md#how-a-run-is-scored) explains each column. The range in
brackets shows how much the figure depends on which tables were drawn.

| Solution | Tables reached | Gain in pickable glasses (90 % range) | Glasses broken | Arm minutes |
|---|---|---|---|---|
| 1–2 Geometry reference | 22 | +5 (0 to +11) | 3 | 14.9 |
| 3 Imitation | 50 | +1 (−2 to +4) | 19 | 10.0 |
| 3 Imitation, with the safety check | 50 | +2 (0 to +4) | 0 | 4.3 |
| 3 Imitation, also copying the ceiling | 50 | +1 (0 to +3) | 8 | 5.3 |
| 3 Imitation, also copying the ceiling, with the safety check | 50 | +1 (0 to +3) | 0 | 2.8 |
| **4 World model** | **50** | **+6 (+2 to +11)** | **2** | **4.6** |
| 5 Reinforcement learning | 43 | +5 (+1 to +10) | 2 | 14.9 |
| 5 Reinforcement learning, with the safety check | 50 | +1 (−4 to +6) | 1 | 5.3 |
| 6 SmolVLA | 50 | +1 (−3 to +6) | 17 | 12.5 |
| 6 SmolVLA, with the safety check | 50 | +0 (−2 to +2) | 5 | 6.1 |
| The ceiling (tries 30 pushes first) | 50 | +24 (+15 to +34) | 0 | 4.8 |

To see what each solution did on one table, open the [runs](../full-arm/runs/results.md)
folder. It keeps the first 25 of these tables one by one: where every glass started, and where
it stood after each solution, as JSON and as a picture. It also lists every push each solution
asked for, with the direction, the settings handed to MoveIt and how the push ended, so you can
see whether the hand came down in the gap between two glasses or at the side.

## What the results say

- **Learning from failures matters most.** The world model learns from every push,
  including the ones that tipped a glass or could not be planned, and reinforcement learning
  is scored on its failures as it practises. So both know which pushes to avoid, and they are
  the only two solutions whose gain is clearly above zero. Reinforcement learning, however,
  spends its arm time on a few tables where it keeps pushing, so it reaches only 43 tables.
- **Copying only successes breaks glasses.** Imitation and SmolVLA never saw a push that
  tipped a glass, so they push glasses that tip. The safety check removes most of that
  breakage. However, it does not add any gain, because a check can only reject pushes and
  cannot propose better ones.
- **The arm cannot make most pushes.** About three pushes in four cannot be planned at all,
  and the push a person would try first is never possible. [What the pushes
  show](what-the-pushes-show.md) explains why.
- **There is much more to find.** The ceiling gains 24 glasses, so the best solution finds
  about a quarter of what is there.
- **One run is noisy, so small differences mean nothing.** These results were measured again
  after the solutions were given the choice of how much to look, with no model trained again.
  Several of them moved by two to four glasses. The cause is not the looking alone: a slightly
  different picture or a different random draw changes a borderline decision, and one
  changed push changes the rest of that table. The range in brackets covers only which
  tables were drawn, not this noise. So a difference of two or three glasses between two
  solutions should not be read as real.

## Films

Each film shows one solution on the same five held-out tables, so the films can be compared
table by table. The tables were chosen so that every solution pushes on every one of them,
and so that on three of them some solutions tip a glass. The words at the top of a film say
how many glasses could be picked at the start and at the end of each table. The table below
gives the same thing for every film: pickable glasses at the start → at the end, and ✗ where
a glass went over.

| Solution | 11158 | 11416 | 11716 | 11952 | 10490 |
|---|---|---|---|---|---|
| 1–2 Geometry reference | 1 → 3 | 1 → 1 | 2 → 1 | 2 → 2 | 1 → 1 |
| 3 Imitation | 1 → 3 | 1 → 0 | 2 → 2 | 2 → 2 ✗ | 1 → 1 ✗ |
| 3 Imitation, with the check | 1 → 3 | 1 → 0 | 2 → 4 | 2 → 2 ✗ | 1 → 1 |
| 4 World model | 1 → 3 | 1 → 3 | 2 → 4 | 2 → 3 | 1 → 3 |
| 5 Reinforcement learning | 1 → 3 | 1 → 3 | 2 → 1 ✗ | 2 → 2 | 1 → 1 |
| 5 Reinforcement learning, with the check | 1 → 3 | 1 → 3 | 2 → 2 | 2 → 2 | 1 → 1 |
| 6 SmolVLA | 1 → 2 | 1 → 3 | 2 → 2 | 2 → 2 | 1 → 0 ✗ |
| 6 SmolVLA, with the check | 1 → 2 | 1 → 3 | 2 → 2 | 2 → 2 | 1 → 1 |

The films were made before the solutions chose how much to look, when every solution
looked from both places on every turn, so a film can differ from what the same solution
does now. Five tables are too few to rank the solutions; the results table above does that. The films
show what the ranking means: on table 10490, for example, imitation and SmolVLA tip a glass,
the check stops SmolVLA in time, and the world model frees both glasses.

Links to the films:

| Solution | Without the safety check | With the safety check |
|---|---|---|
| 1–2 Geometry reference | [film](../videos/full-arm/1-2-geometry-reference.mp4) | |
| 3 Imitation | [film](../videos/full-arm/3-imitation.mp4) | [film](../videos/full-arm/3-imitation-with-check.mp4) |
| 4 World model | [film](../videos/full-arm/4-world-model.mp4) | |
| 5 Reinforcement learning | [film](../videos/full-arm/5-reinforcement-learning.mp4) | [film](../videos/full-arm/5-reinforcement-learning-with-check.mp4) |
| 6 SmolVLA | [film](../videos/full-arm/6-smolvla.mp4) | [film](../videos/full-arm/6-smolvla-with-check.mp4) |

## Read in this order

1. [The problem](problem.md): the tables, what "finished" and "broken" mean, and the scoring.
2. [The arm and MoveIt](the-arm-and-moveit.md): job 3, and how the arm looks.
3. [The box model](the-box-model.md): job 0.
4. [What the pushes show](what-the-pushes-show.md): the data, and what it says about pushing.
5. The solution pages, in the order of the table above.

The code is in [`04-clear-the-table/full-arm/`](../full-arm/README.md).
