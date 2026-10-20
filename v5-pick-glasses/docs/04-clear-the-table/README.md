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

Jobs 1 and 2 are one answer. A solution is asked once a turn, and it replies with one
**push**: this glass, this direction, this distance, and six settings such as how high
and how fast the hand moves. It may also reply that the table is **finished**.

## One turn

The arm looks at the table from two places, because a glass hidden behind another glass
is missing from one picture. The box model turns each picture into boxes. The solution
answers with a push or with "finished". MoveIt plans the push as four motions, and the
arm carries them out in the MuJoCo physics engine. Then the next turn starts.

![The same table from the two viewing places, with the boxes the box model drew](../../images/04-clear-the-table/full-arm-two-views-and-boxes.png)

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
| 1–2 Geometry reference | 22 | +2 (−2 to +7) | 4 | 15.0 |
| 3 Imitation | 47 | +3 (0 to +7) | 19 | 15.0 |
| 3 Imitation, with the safety check | 50 | +3 (+1 to +6) | 1 | 4.7 |
| 3 Imitation, also copying the ceiling | 50 | +0 (−2 to +2) | 8 | 7.1 |
| 3 Imitation, also copying the ceiling, with the safety check | 50 | +2 (0 to +4) | 0 | 3.0 |
| **4 World model** | **50** | **+9 (+3 to +15)** | **2** | **4.9** |
| 5 Reinforcement learning | 50 | +3 (0 to +7) | 3 | 12.7 |
| 5 Reinforcement learning, with the safety check | 50 | +0 (−4 to +4) | 1 | 5.0 |
| 6 SmolVLA | 50 | −3 (−7 to 0) | 22 | 14.0 |
| 6 SmolVLA, with the safety check | 50 | −1 (−6 to +4) | 0 | 7.7 |
| The ceiling (tries 30 pushes first) | 50 | +24 (+15 to +34) | 0 | 4.8 |

## What the results say

- **Learning from failures matters most.** The world model learns from every push,
  including the ones that tipped a glass or could not be planned. So it knows which pushes
  to avoid, and it is the only solution whose gain is clearly above zero.
- **Copying only successes breaks glasses.** Imitation and SmolVLA never saw a push that
  tipped a glass, so they push glasses that tip. The safety check removes almost all of that
  breakage. However, it does not add any gain, because a check can only reject pushes and
  cannot propose better ones.
- **The arm cannot make most pushes.** About three pushes in four cannot be planned at all,
  and the push a person would try first is never possible. [What the pushes
  show](what-the-pushes-show.md) explains why.
- **There is much more to find.** The ceiling gains 24 glasses, so the best solution finds
  about a third of what is there.

## Films

Each film shows one solution clearing the same five held-out tables:
[geometry reference](../../videos/04-clear-the-table/full-arm/1-2-geometry-reference.mp4),
[imitation](../../videos/04-clear-the-table/full-arm/3-imitation.mp4),
[world model](../../videos/04-clear-the-table/full-arm/4-world-model.mp4) and
[reinforcement learning](../../videos/04-clear-the-table/full-arm/5-reinforcement-learning.mp4).

## Read in this order

1. [The problem](problem.md): the tables, what "finished" and "broken" mean, and the scoring.
2. [The arm and MoveIt](the-arm-and-moveit.md): job 3, and how the arm looks.
3. [The box model](the-box-model.md): job 0.
4. [What the pushes show](what-the-pushes-show.md): the data, and what it says about pushing.
5. The solution pages, in the order of the table above.

The code is in [`04-clear-the-table/full-arm/`](../../04-clear-the-table/full-arm/README.md).
