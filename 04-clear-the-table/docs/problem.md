# The problem

This page states what the arm is asked to do and how a run is scored. Every solution is
judged by the same rules, so the rules are written once, here. By the end you will know
what is on a table, what counts as "finished" and as "broken", and what each column of the
[results table](README.md#results) means.

## What is on a table

Each table holds three to five glasses, all of one kind. There are four kinds: straight,
tapered, stemmed and short stemmed, and the kind changes with the table's number. Every
table has two parts:

- **One touching group** of two or three glasses. These stand too close together for the
  gripper. A group of three is harder than a pair, because moving the middle glass can
  leave the outer two still touching, so the order of the pushes matters.
- **One or two glasses that already have room.** The right thing to do with these is
  nothing.

The number of crowded glasses stays in a narrow band, so tables are alike enough to
compare solutions on. The layout changes from table to table, so a learned model cannot
memorise one arrangement.

## What "room" means

A glass is **pickable** when the open gripper can close round it without touching a
neighbour. The test measures from the glass's middle to the nearest edge of each
neighbour, and it uses the glass's measured width. [Problem 3 derives
it](../../03-push-glasses-apart/docs/problem.md#the-gap-that-matters-is-not-the-gap-between-the-glasses).
No glass's size is written down anywhere in this project: the arm measures every glass
during the run.

## What a solution sees and answers

A solution is not shown the table. It is handed three things: an **arm**, which can move
to a pose and make a push; a **camera** on the arm's wrist, which takes a picture from wherever
the hand is; and a **clock**, which says how much arm time is left. Together these are called
a **run**, one attempt at one table. The solution decides when and where to take pictures,
and the [box model](the-box-model.md) turns each picture into boxes. Most solutions read the
boxes, and SmolVLA reads the pictures. Nothing else from the simulator reaches a solution.
It is not even told the table's number, because that number is the random seed that drew
the glasses.

The **examiner** is the other side of the run. It builds the table, keeps the clock, and
marks the table when the run ends. A run ends in one of three ways: the solution says
"finished", a glass goes over, or the arm time runs out. Nothing outside the solution
decides when a table is done.

The arm time also counts as run out once a solution has asked for a fixed number of pushes
on one table, refused pushes included. This limit exists because a push that MoveIt refuses
costs no arm time, so without it a solution that kept asking for impossible pushes would
never be stopped by the clock. A solution that never says "finished" uses up its arm time,
and one that says it too early is scored on the crowded table it left.

## The budget is arm time

The whole list of tables shares 15 minutes of arm motion. Looking costs arm time, because
the camera is on the arm: the trip to a place to look from, and a quarter of a second for
each picture, while the arm stands still. A push that MoveIt cannot plan costs nothing, because the arm
does not move. Thinking time is recorded but not charged. A solution that wastes time
reaches fewer tables, which is why some rows of the results reach fewer than 50.

## When a glass goes over

A glass that tips over ends that table, and the run moves on to the next one. The glass is
counted as **broken**. The table is also left out of the pickable count, at both the start
and the end, so breaking a glass can never raise a score.

## How a run is scored

| Column | What it counts |
|---|---|
| Tables reached | how far down the list the 15 arm minutes went |
| Gain in pickable glasses | pickable glasses at the end minus at the start, on the tables where nothing went over |
| Glasses broken | glasses that tipped over |
| Arm minutes | arm time used, out of 15 |

Each solution walks the list once, so the only spread is from which tables happened to be
in the list. The 90 % range is found by drawing the 50 tables again with replacement 2,000
times and working the gain out each time. A difference smaller than the range has not been
shown to be real.

## Training tables and held-out tables

Every table is made from its number, so the same number always gives the same table.

| Table numbers | Used for |
|---|---|
| below 10,000 | collecting pushes, training and trying ideas |
| 2,000 to 2,023 | setting each solution's few hand-chosen numbers |
| 10,000 to 10,049 | the results, and nothing else |

Nothing is trained, chosen or tuned on the held-out tables. That is why a result on them
can be trusted to say how a solution does on tables it has never seen.
