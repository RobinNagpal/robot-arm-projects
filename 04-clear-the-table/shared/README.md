# Problem 4 — the code the solutions share

This folder holds the code that several solutions use but that is not part of the examiner. The
examiner, in [`../examiner/`](../examiner/README.md), is the cell and the marks: what a solution
is given and how its table is judged. What is here is on the solutions' side of that line. It is
how a solution sees, how it takes its turns, and how the learned solutions write a table down
as numbers. By the end of this page you will know what each package holds and why it lives
here rather than in one solution's folder.

## Why this code is shared

Every solution has to turn the wrist pictures into glasses before it can choose a push, and
every solution takes the table one turn at a time: look, choose, push, and say when it is done.
Writing those parts again in each solution folder would let them drift apart, and then a
difference between two solutions could be a difference in how they see rather than in how they
choose. So they are written once, here, and the solution folders hold only what makes each
solution different.

## The packages

**`turn_by_turn_loop.py`** is the loop that every solution is built on. A solution only says what
to do with one look, and the loop does the looking, carries out the push and asks again.
It also holds the two ways of looking that a solution can choose between: looking only as much
as it needs, or looking from both viewing places on every turn.

**`seeing`** is job 0, the box model: a small network that reads a wrist picture and draws a box
round every glass in it, so that MoveIt can plan round the glasses and a solution can choose
between them. It holds the model, the program that photographs training tables to make its
pictures and answer keys, and the program that trains it. Its trained weights are in
`seeing/weights/`.

| File | What it is |
|---|---|
| `seeing/box_model.py` | the box model: from a picture to boxes on the table |
| `seeing/make_box_training_data.py` | photographs training tables from both viewing places, with the answer keys |
| `seeing/train_box_model.py` | trains the box model and measures it on pictures it has not seen |

**`learning`** is what the learned solutions have in common: how a table and a push are written
as numbers, the small networks they are built from, and the pushes they learn from. Those
pushes were made by the arm in the physics, and they are kept in `learning/data/` because
imitation, the world model and SmolVLA all learn from the same ones.

| File | What it is |
|---|---|
| `learning/table_and_push_encoding.py` | how a table and a push are written as numbers, and read back |
| `learning/learned_networks.py` | the small networks the learned solutions use |
| `learning/collect_training_pushes.py` | pushes made at random, informed, or chosen by a model, and what happened to each |

## How it is used

A solution folder imports what it needs from here by package name, for example
`from shared.turn_by_turn_loop import TurnByTurn`. This code in turn uses the examiner's contract, because
a solution reaches the arm only through that contract. The examiner never imports anything from
here, apart from the tools that run the solutions.
