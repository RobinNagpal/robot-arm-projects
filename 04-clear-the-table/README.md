# Problem 4 — clear the table

Problem 4 asks for problem 3's task again. Some glasses on the table stand too
close together for the gripper to close round one without touching its
neighbour, so the arm has to push them apart across the table instead of
lifting them. What makes it a new problem is what has been taken away. This
page says what those two changes are, how the folder is laid out, and where to
start reading. By the end you will know which folder holds the current answer,
which folders hold the first version, and how to run each one.

## What is taken away

Problem 3 gave a solution two kinds of help from outside the arm, and problem 4
removes both of them.

**The camera above the table is gone.** The arm carries its own camera on its
wrist, so seeing costs motion and time. A solution that wants to know what is in
the far corner of the table has to take the arm there first. An overhead camera
is a convenience of the simulator, and the cell this project is built for does
not have one.

**The push-by-push hand-over is gone.** In problem 3, something outside the
solution asked for one push, carried it out, marked it and asked again. Here a
solution is handed the arm and a clock and works through the table on its own:
it looks, it pushes, it looks again, and it **says when the table is finished**.
Nothing else decides that the work is done, because a real cell has nobody
standing by to count the pushes. The table is then marked once, on how the
glasses stand when the solution stopped.

## Two cells, built one after the other

Problem 4 was built twice, and the two versions differ in how the hand moves.
Both use the same drawn tables, the same glasses and the same rules for
marking a table, so their numbers are read on the same scale.

**The whole-arm cell is the current answer.** A UR5e arm stands at the table in
the MuJoCo physics engine, and MoveIt 2, a standard motion planner for robot
arms, plans every motion it makes. A solution never writes a joint angle. It
chooses which glass to push, which way, how far, and the settings MoveIt is
given, and MoveIt finds a path for the arm that avoids every glass. The code is
in [`full-arm/`](full-arm/README.md), and the documents in
[`docs/`](docs/README.md) are about this cell. Start with
[`docs/README.md`](docs/README.md), which gives the whole picture and every
result.

**The first cell moves the jaw on its own.** Before the whole arm was built,
problem 4 was solved in a simpler cell in which the gripper's jaw follows a
list of waypoints with no arm behind it. A solution there writes the jaw's path
itself, and no planner checks it first. Its shared parts are in [`examiner/`](examiner/README.md), its solutions
are in the numbered folders, and [`results/`](results/README.md) sets them side
by side. Each of those folders has its own `README.md`, which is that
solution's full description. The whole-arm cell is built on this one: it reuses
the first cell's table draw, its wrist camera, its physics settings and its
scorecard.

**The first cell's solutions also run on the arm.** Each of them answers with a
path for the jaw, and [`full-arm/jaw_solutions.py`](full-arm/jaw_solutions.py)
hands that path to the UR5e, where MoveIt carries it out as straight motions
planned before the arm moves. They keep their own trained weights, so `make
evaluate-jaw` in `full-arm/` measures the same solutions on the arm. They have
not been measured there yet.

The first cell once had longer documents of its own in `docs/`, such as the
description of how its tables are marked and the record of every change made
to its solutions. They were removed when `docs/` was rewritten for the whole
arm, because two sets of documents for one problem made the current answer
hard to find. Where a first-cell page still needs one of them, it links to the
page as it stood before it was removed, on GitHub.

## What is in this folder

```
docs/                               the documents for the whole-arm cell
full-arm/                           the whole-arm cell: the UR5e, MoveIt 2, the box model and the solutions
  ros/                              the separate ROS environment MoveIt runs in
images/  videos/                    the pictures and films the documents show
examiner/                              the first cell's shared parts: the draw, the camera, the loop, the scorecard
01-one-fixed-nudge/                 first cell: the geometry reference
02-geometry-ranked/                 first cell: the same loop, with fitted trees ordering the pushes
03-imitation-from-demonstrations/   first cell: a gate that decides and a chunked policy that draws the path
04-a-world-model/                   first cell: a fitted model of what a push does, and a search
06-smolvla-fine-tuned/              first cell: SmolVLA with a small correction fitted on this cell
demonstrations/                     the teacher's answers, for the first cell's two fitted solutions
results/                            the first cell's solutions side by side
work-cell/                          this problem's copy of problem 1's modules for the table, arm, glasses and rack
from-problem-3/                     this problem's copy of the problem 3 files it is built on
pixi.toml  ruff.toml  Makefile      the environment and the commands
```

There is no folder numbered 05 among the first cell's solutions. It held
SmolVLA as it downloads, with nothing fitted, and it was retired when the
whole-arm cell was built.

## It shares no code with other problems

Problem 4 builds on problems 1 and 3, but it does not import anything from
their folders. Instead it keeps its own copy of exactly the files it uses, in
`work-cell/` and `from-problem-3/`, and its own ROS environment in
`full-arm/ros/`. This means the folder can be read, run and changed on its own.

Problem 4 copies only what it needs. Problem 3 keeps the part of its examiner that
both problems share in its own `common_bench.py`, `common_scoring.py` and
`common_film.py`, and the parts that belong to problem 3 alone, such as its
overhead camera, in the files that extend them. Problem 4 copies the three
common files, and its own `examiner/simulator.py`, `scoring.py` and `film.py` extend
them in the same way.

A copy has one cost: it does not change when the original changes. Problem 4's
results are compared with problem 3's, and that comparison holds only while the
two cells agree, so the copies are kept exactly as the originals and are never
edited here. [`from-problem-3/README.md`](from-problem-3/README.md) lists what
was copied and what uses each file.

## How to run it

`make help` in this folder lists the commands for the first cell, and
`make help` in `full-arm/` lists the commands for the whole-arm cell. In both,
`make test` runs the tests that need no simulator, and `make lint` runs Ruff,
a Python style checker. The whole-arm cell also needs the ROS environment once,
which `make ros` in `full-arm/` builds, and after that every command starts
MoveIt by itself.

Keep test runs short. The tests are meant to take a handful of tables and a few
seconds of simulated arm time, because the same machine is used to train the
models.
