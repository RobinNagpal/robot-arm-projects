# Solution 3 — imitation

This folder holds the solution that learns by copying. It is shown pushes that worked, and it
is trained to answer the same way on a table it has not seen. By the end of this page you will
know what this folder holds and how to train and score the solution.

## What it learns from

Its main examples are the pushes the arm really made, kept in
[`../shared/learning/data/`](../shared/README.md) because every learned solution reads
them. From those, imitation keeps only the pushes that
worked. It can also copy a second kind of example: lessons written by the ceiling, the search
that tries thirty pushes in the physics before each move. A real arm cannot try a push first,
so the ceiling cannot be a solution, but it can be a teacher, and [`lessons_from_ceiling.py`](lessons_from_ceiling.py) runs
it on training tables to write those lessons. Copying a slow search with a fast network like
this is called distillation.

Because it copies only successes, imitation never sees a push that tipped a glass, so it
breaks glasses. The safety check in [`../04-world-model/`](../04-world-model/README.md) is
what stops most of that.

The full explanation, and what it scores, is on its page in the documents:
[imitation](../docs/solutions/03-imitation.md).

## What is in this folder

| File | What it is |
|---|---|
| [`imitation.py`](imitation.py) | the network, its training, and the solution that uses it |
| [`lessons_from_ceiling.py`](lessons_from_ceiling.py) | the ceiling run on training tables, writing lessons to copy |
| `weights/` | the trained networks; `imitation-r4.pt` is the one the results report |
| `data/` | the ceiling's lessons |
| `results/` | the record of each training run |

## Running it

From the problem folder:

```
make imitation                                # train it on the four rounds of pushes
make evaluate-imitation TABLES=50             # score it on the held-out tables
```
