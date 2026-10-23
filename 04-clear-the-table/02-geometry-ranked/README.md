# Solution 2 — geometry ranked

This folder holds solution 1 with one decision changed. Solution 1 always makes the shortest
safe push that gives a glass room. This solution scores every safe push with problem 3's fitted
trees and makes the one with the best score. Everything else, from the list of safe pushes to
the fixed settings handed to MoveIt, is solution 1's. By the end of this page you will know
where its parts come from and how to score it.

## How it works

The list of safe pushes and the trees both come from problem 3's ranked solution, kept as exact
copies in [`../from-problem-3/`](../from-problem-3/README.md). The trees are problem 3's own
fitted file, loaded and not fitted again, so a difference between the two problems comes from
the arm and not from a new fit. The fitted file is kept in git there, as an exact copy of the
one problem 3 makes with `make train` in its `02-geometry-ranked` folder.

On the arm, the pushes the trees prefer tip glasses far more often than the ones solution 1
chooses. The full explanation, and what it scores, is on its page in the documents:
[geometry ranked](../docs/solutions/02-geometry-ranked.md).

## What is in this folder

| File | What it is |
|---|---|
| [`geometry_ranked.py`](geometry_ranked.py) | the solution: solution 1 with problem 3's trees choosing the push |

## Running it

From the problem folder:

```
make evaluate-geometry-ranked TABLES=50       # score it on the held-out tables
```
