# Problem 4 — clear the table

Problem 4 asks for problem 3's task again. Some glasses on the table stand too close together
for the gripper to close round one without touching its neighbour, so the arm has to push them
apart across the table instead of lifting them. What makes it a new problem is what has been
taken away, and that a whole UR5e arm now does the pushing. This page says what those changes
are, how the folder is laid out, and where to start reading. By the end you will know which
folder holds the cell, which folders hold the solutions, and how to run each one.

## What is taken away

Problem 3 gave a solution two kinds of help from outside the arm, and problem 4 removes both of
them.

**The camera above the table is gone.** The arm carries its own camera on its wrist, so seeing
costs motion and time. A solution that wants to know what is in the far corner of the table has
to take the arm there first. An overhead camera is a convenience of the simulator, and the cell
this project is built for does not have one.

**The push-by-push hand-over is gone.** In problem 3, something outside the solution asked for
one push, carried it out, marked it and asked again. Here a solution is handed the arm and a
clock and works through the table on its own: it looks, it pushes, it looks again, and it **says
when the table is finished**. Nothing else decides that the work is done, because a real cell
has nobody standing by to count the pushes. The table is then marked once, on how the glasses
stand when the solution stopped.

## The arm, and who decides what

A UR5e arm stands at the table in the MuJoCo physics engine, and MoveIt 2, a standard motion
planner for robot arms, plans every motion it makes. A solution never writes a joint angle. It
chooses which glass to push, which way, how far, and the settings MoveIt is given, and MoveIt
finds a path for the arm that avoids every glass. So the solutions compete on deciding, and the
moving is done the same way for all of them. The documents in [`docs/`](docs/README.md)
explain this in full; start with [`docs/README.md`](docs/README.md), which gives the whole
picture and every result.

## What is in this folder

The folder follows the same plan as problem 3's: one folder for the cell that every solution
runs in and is marked by, one for the code the solutions share, and one numbered folder for
each solution.

```
docs/                               the documents: the problem, the arm, the box model, the data and each solution
examiner/                           the cell and the marks, in four packages:
  simulation/                       the table, the glasses, the UR5e and its wrist camera, in the physics engine
  motion/                           MoveIt 2, and a push as MoveIt motions
  examining/                        what a solution is given, the examiner behind it, and the scorecard
  tools/                            scoring, comparing, recording and filming the solutions, and the ceiling
  ros/                              the separate ROS environment MoveIt runs in
shared/                             the code the solutions share:
  seeing/                           the box model, which finds the glasses in a picture
  learning/                         how the learned solutions write a table down, and the pushes they learn from
tests/                              the checks that need neither MoveIt nor a long run of the physics
01-geometry-reference/              solution 1: problem 3's shortest safe push, with fixed settings
02-geometry-ranked/                 solution 2: the same safe pushes, ordered by problem 3's fitted trees
03-imitation/                       solution 3: copies the pushes that worked
04-world-model/                     solution 4: learns what a push does, then searches; also the safety check
05-reinforcement-learning/          solution 5: learns by trying pushes and being scored
06-smolvla-fine-tuned/              solution 6: SmolVLA with a small correction fitted to answer with a push
images/  videos/                    the pictures and films the documents show
work-cell/                          this problem's copy of problem 1's modules for the table, arm, glasses and rack
from-problem-3/                     this problem's copy of the problem 3 files it is built on
pixi.toml  ruff.toml  Makefile      the environment and the commands
```

Each solution folder has its own `README.md`, which says what is in it and how to train and
score it, and each one links to that solution's page in `docs/`.

## It shares no code with other problems

Problem 4 builds on problems 1 and 3, but it does not import anything from their folders.
Instead it keeps its own copy of exactly the files it uses, in `work-cell/` and
`from-problem-3/`, and its own ROS environment in `examiner/ros/`. This means the folder can be
read, run and changed on its own.

Problem 4 copies only what it needs. Problem 3 keeps the part of its examiner that both problems
share in its own `common_bench.py` and `common_scoring.py`, and the parts that belong to problem
3 alone, such as its overhead camera, in the files that extend them. Problem 4 copies the common
files, and its own `examiner/simulation/table_simulator.py` and `examiner/examining/table_scoring.py`
build on them.

A copy has one cost: it does not change when the original changes. Problem 4's results are
compared with problem 3's, and that comparison holds only while the two push the same glasses
with the same physics, so the copies are kept exactly as the originals and are never edited
here. [`from-problem-3/README.md`](from-problem-3/README.md) lists what was copied and what uses
each file.

## How to run it

Every command runs from this folder, and `make help` lists them all. `make test` runs the tests
that need neither MoveIt nor a long run of the physics, and `make lint` runs Ruff, a Python
style checker. MoveIt also needs its ROS environment, which `make ros` builds once, and after
that every command starts MoveIt by itself.

Keep test runs short. The tests are meant to take a handful of tables and a few seconds of
simulated arm time, because the same machine is used to train the models.
