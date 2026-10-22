# Robot arm projects

This repo holds robot arm projects that run entirely in simulation, so none of
them needs hardware to try. The first six folders are one task, taken apart
into six problems: a UR5e arm has to measure the drinking glasses on a table,
pick each one up, turn it over and stand it on a drying rack. The seventh is a
separate project, in which the arm learns to pick up a block and place it.
This page says what each folder is, why the six problems come in the order
they do, and where to start reading.

| Folder | What the arm does | State |
| --- | --- | --- |
| [`01-rack-one-glass`](01-rack-one-glass/README.md) | Measures one glass, picks it up, turns it over and stands it on the rack | **built**, in Gazebo |
| [`02-segment-glasses`](02-segment-glasses/docs/README.md) | Tells several glasses of one kind apart, as a set of pixels per glass | six solutions built |
| [`03-push-glasses-apart`](03-push-glasses-apart/docs/README.md) | Drags glasses that stand too close apart, until each can be gripped | seven solutions built |
| [`04-clear-the-table`](04-clear-the-table/docs/README.md) | Does the same with only the arm's own camera, and says itself when it has finished | built on a UR5e with MoveIt 2, six solutions |
| [`05-rack-several-kinds`](05-rack-several-kinds/docs/README.md) | Racks every glass on a table that holds several kinds at once | learned version built |
| [`06-unknown-proportions`](06-unknown-proportions/docs/README.md) | The same, for glasses whose proportions are written down nowhere | stated |
| [`07-learn-pick-place`](07-learn-pick-place/README.md) | Picks up an irregular block and places it on a target, with the movement learned from demonstrations | working: 74 % on unseen blocks in MuJoCo |

**Each folder stands on its own.** It has its own environment, its own code,
its own documents, pictures and films, and its own `Makefile`. No folder
imports code from another. Where a problem builds on an earlier one, it keeps
its own copy of the files it uses, so that each folder can be read, run and
changed without the others.

## The six glass problems

The glass task is not one problem. It is six, and they get harder in a
particular way: **each one takes away something the one before it was allowed
to assume.**

![The six problems, and what each one adds](01-rack-one-glass/images/the-six-problems.png)

Read [`problem-statement.md`](01-rack-one-glass/problem-statement.md) first if
you have not. It says what the task is, why glasses were chosen, what the arm
is allowed to know, and what counts as done. Everything in the six folders
follows from it.

| | Problem | Where it stops | State |
| --- | --- | --- | --- |
| **1** | [One glass, start to finish](01-rack-one-glass/docs/README.md) | the glass is on the rack | **built** |
| **2** | [Segment the glasses](02-segment-glasses/docs/README.md) | a set of pixels per glass | six solutions built |
| **3** | [Glasses standing too close](03-push-glasses-apart/docs/README.md) | the glasses are far enough apart to grip | seven solutions built |
| **4** | [Clear the table](04-clear-the-table/docs/README.md) | every glass has room, and the arm has said so | built on a UR5e with MoveIt 2, six solutions |
| **5** | [Several kinds at once](05-rack-several-kinds/docs/README.md) | the table is clear | learned version built |
| **6** | [Kinds whose proportions are unknown](06-unknown-proportions/docs/README.md) | the table is clear | stated |

## Why they are in this order

Each problem is the one before it with one assumption removed, so each answer
is something the next problem can stand on.

**Problem 1** has one glass on a bare table. Nothing hides anything, the camera
can go wherever it likes, and the glass is reachable where it stands. That
leaves the difficulties that are about the *object* rather than about the
scene. Its size has to be measured. Its weight cannot be seen at all. There is
usually only one place it may be held. And the set-down has to be felt rather
than driven.

**Problem 2** puts several glasses of the same kind on the table. The kinds are
known, so naming is not the difficulty. Telling one glass from another is — and
worse, the arm can no longer photograph each one from whichever side it likes,
because the other glasses are in the way of the camera or of the arm.

**Problem 3** starts from problem 2's answer. Some of those glasses are close
enough together that the gripper cannot get round one without fouling its
neighbour. They have to be moved apart by **dragging them across the table**,
because lifting one is the thing that is not possible yet.

**Problem 4** keeps problem 3's task and takes away the help that came from
outside the arm. In problem 3 a camera fixed above the table sees every glass
at once, and the arm is handed one push at a time: something outside it decides
whether that push may be carried out, marks it, and says when the table is
finished. Neither of those is part of the arm. Here the only camera is the one
the arm carries, so looking at a corner of the table costs a movement, and
nothing is handed over push by push. The arm looks, pushes, looks again, and
says for itself when it has finished. The table is then marked once, on how
the glasses are arranged when the arm stopped. It ends where problem 3 ends,
with every glass given room, so problem 5 can stand on either answer.

**Problem 5** joins the first three up and adds the part none of them has:
several kinds at once, so the rule changes per glass and naming the kind
becomes load-bearing.

**Problem 6** takes away the proportions. The kinds are still the four shapes,
but no two glasses of a kind are alike and nothing is written down. This is the
problem the whole project exists for, and the reason every earlier problem
refuses to record a measurement.

## What is in each folder

Each problem folder keeps its documents in `docs/`, and `docs/problem.md`
states the problem in full — what
is on the table, what the arm is not told, what makes it hard, and what "done"
means. After that they differ, because the problems do:

- **Problems 1, 5 and 6** are the whole pipeline, so they are written as the
  same six *steps*: find it, measure it, name it, choose the grip, squeeze,
  turn it over. Problem 1 gives each step a document of its own, because it is
  built. Problems 5 and 6 take the six as a section of `problem.md`, saying
  what changes at each and nothing else.
- **Problems 2 and 3** are not the whole pipeline and do not have all the
  steps. Problem 2 stops at a set of pixels per glass; problem 3 stops at
  glasses far enough apart to be gripped. Each has a `solution-overview.md`
  instead — nine and eleven solutions respectively, grouped as programmed,
  hybrid and learned, with which one is chosen and why. Both open with the three
  ideas the comparisons turn on. Where a learned part can sit in a pipeline.
  What it takes for a machine to choose its own next measurement. And the rule
  that every solution in them can be built inside the simulator. Each
  folder also has a `learned-with-hardware.md` holding the answers that cannot
  — a foundation model, a fine-tune, a reinforcement-learning policy — beside
  the condition each one fails.
- **Problem 4** does not pick anything up either, so it has no six steps. Its
  `README.md` holds the whole picture and every result, `problem.md` says how a
  run is scored, three pages explain the arm, the box model and the data, and
  `solutions/` has one short page per solution.
- **Problem 5** has both: the six steps in `problem.md`, and a `solutions/`
  folder with a `solution-overview.md` and nine solutions, split into
  `programmed/` and `learned/` as problem 2's are. Most of them are
  combinations of problem 1, 2 and 3 pieces, and the overview says which piece
  sits at which stage of a run. The learned one is built, in
  [`08-learned-pipelines`](05-rack-several-kinds/08-learned-pipelines/README.md).

## What does not work yet

[`known-gaps.md`](01-rack-one-glass/docs/known-gaps.md) lists the failures that are known but not yet
fixed, such as the glass sizes the grip rules cannot handle. It is about the
code as it stands, which is to say about problem 1.

## The cell

[**The cell**](01-rack-one-glass/docs/the-cell.md) describes the room every problem works in: the
layout with its dimensions, the two poses the camera is ever put in, all four
sensors, the four kinds of glass, and the vocabulary — survey, station,
standoff, nadir, splay, footprint. Every number on it is read from the
project's own constants rather than typed in. The solution documents point at
it rather than restating it.

## The pictures

Every diagram in these documents is drawn by a script, and each problem keeps
its scripts in its own `images/generators/` folder, next to the pictures they
write. Nothing here is a hand-drawn picture kept in step by hand.

Problem 1's [`make_images.py`](01-rack-one-glass/images/generators/make_images.py)
draws the problem-1 walkthrough by importing problem 1's own modules and
plotting what they return, so if a rule changes, the picture changes with it
the next time the script is run.
[`make_problem_images.py`](01-rack-one-glass/images/generators/make_problem_images.py)
draws the diagrams that describe the problems themselves. Problems 2, 3 and 4
have generators of their own, which compute their own geometry or read their
own results, so the arithmetic in a picture and the arithmetic in the prose
beside it come from the same numbers.

## Where the techniques come from

None of the perception or the gripping here is invented for this project. Each
step is one named technique, and the places they are set out side by side are
the **object perception** and **gripping** areas of robotics-basics:
[finding and measuring](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/01_overview.md)
and [gripping](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/01_overview.md).
[The problem-1 walkthrough](01-rack-one-glass/docs/README.md#where-the-techniques-come-from)
has the full map, and every document links to the sections it uses.

There is also a design document for this exact task, written before any of the
code: [standing an empty glass upside down on a drying
rack](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/10_one-arm-training/07_case-study/01_place-glass.md).

## 07 — learn to pick and place

An irregular block lies somewhere on the table and a red target somewhere
else, and the arm picks the block up and sets it down on the target. Here the
movement is learned rather than written: a scripted expert does the job a few
hundred times, every joint angle it commands is recorded, and an ACT policy
(Action Chunking with Transformers, from LeRobot) learns to do the same from
the arm's joint angles and where the block is. The block is found with plain
geometry from a depth camera. It runs in MuJoCo instead of Gazebo, because
learning from demonstrations needs hundreds of fast, repeatable episodes.

→ [`07-learn-pick-place/README.md`](07-learn-pick-place/README.md)
