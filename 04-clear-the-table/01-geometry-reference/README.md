# Solution 1 — the geometry reference

This folder holds the reference solution. Nothing in it is learned: problem 3's geometry
chooses which glass to push, which way and how far, and one fixed set of settings goes to
MoveIt every time. It exists so that every learned solution has a number to be compared with,
and [solution 2](../02-geometry-ranked/README.md) is this same solution with a different way of
choosing the push. By the end of this page you will know where its parts come from and how to
score it.

## How it works

The solution reads the boxes the box model found, turns each box back into the measurements
problem 3's planner reads, and asks that planner for a push. Problem 3's planner is used as it
is, from this problem's copy in [`../from-problem-3/`](../from-problem-3/README.md), so a
difference between the two problems is the arm and not the geometry. The solution only tells
the planner two things about the arm's cell: where the arm's hand has its top edge, which is
10 mm higher than problem 3's, and which glasses already have room and so are left alone. The
loop that looks, pushes and says when the table is finished is the one every solution shares,
in [`../shared/turn_by_turn_loop.py`](../shared/turn_by_turn_loop.py).

The full explanation, and what it scores, is on its page in the documents:
[the geometry reference](../docs/solutions/01-geometry-reference.md).

## What is in this folder

| File | What it is |
|---|---|
| [`geometry_reference.py`](geometry_reference.py) | the solution: problem 3's shortest safe push, with one fixed set of settings |

## Running it

From the problem folder:

```
make evaluate-geometry TABLES=50              # score it on the held-out tables
```
