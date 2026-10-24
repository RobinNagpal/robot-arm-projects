# Problem 4 — the examiner

This folder holds the examiner: the cell that every solution of problem 4 runs in, and the
part that marks what each solution did. A UR5e arm stands at a table in the MuJoCo physics
engine, **MoveIt 2 plans every motion it makes**, and a camera rides on its wrist. A solution
reaches all of this only through a small contract, and the examiner keeps everything else to
itself, such as where the glasses really are. The solutions are in the numbered folders beside
this one, and the code they share, such as the box model, is in [`../shared/`](../shared/README.md).
By the end of this page you will know how the work is split, what a solution is given, and
which package holds which part.

## The four jobs

Clearing a table is split into four jobs. Only the middle two are the solutions' own, because
those are the decisions the solutions compete on, and the other two are done the same way for
every solution.

| | Job | Who does it | Where |
|---|---|---|---|
| 0 | Find a box round each glass, so MoveIt can plan round it | a network that reads the wrist picture | [`../shared/seeing/`](../shared/README.md) |
| 1 | Decide which glass to move and where it should go | the solution | the numbered folders |
| 2 | Choose the settings handed to MoveIt so that the glass does not tip | the solution | the numbered folders |
| 3 | Move the arm | **MoveIt 2**, nothing else | [`motion/`](#the-four-packages) |

Jobs 1 and 2 are one answer, because on each turn a solution chooses a single push: *this
glass, this way, this far, with these six settings*. The six are the ones MoveIt itself is
given. A solution never writes a joint angle.

## What a solution is given

Because a real cell has nobody standing by to hand over pictures or count pushes, a solution
is handed a **run** and nothing else: an arm with a wrist camera, and a clock. It decides when
and where to look, which push to ask for, and when the table is finished. The examiner is the
other side of that contract. It builds the table, keeps the table's number to itself, charges
the arm time, ends the run when a glass goes over or the time runs out, and marks the table.

## The four packages

The examiner's files are grouped by what they are about, in four packages. You can read them
from the bottom up, because each package uses only the ones before it, like layers in a stack.

**`simulation`** is the world: the table, the glasses, the arm and the camera, in the physics
engine. Problem 3's physics comes in through `taken_from_problem_3.py`, which is the only file that reaches
into this problem's copy of problem 3 ([`../from-problem-3/`](../from-problem-3/README.md)), so
the whole debt to problem 3 can be read on one page. `table_simulator.py` extends problem 3's common
simulator with problem 4's own draw of tables, from `table_draw.py`, and `arm_and_table_simulator.py`
extends that with the UR5e. Each layer keeps what the one below it does and adds one thing,
in the same way that a subclass extends a class.

| File | What it is |
|---|---|
| `taken_from_problem_3.py` | everything taken from the copy of problem 3, in one place |
| `table_simulator.py`, `table_draw.py` | one of problem 4's tables in the physics engine, and the draw of its glasses |
| `ur5e_model.py` | the UR5e as a MuJoCo model, read out of the same URDF MoveIt plans on |
| `arm_and_table_simulator.py` | the table and the arm, with joint servos, following a joint trajectory |
| `wrist_camera.py` | the wrist camera, and which glasses it can really see from a pose |

**`motion`** is job 3: how the arm is moved. MoveIt needs a ROS environment, and the physics and
the learning need problem 4's, so MoveIt runs in the ROS environment kept in
[`ros/`](ros/README.md), as a small server, and everything else talks to it over a pipe, one
JSON line each way. What crosses is a goal pose and some settings in, and a list of joint
angles with times out.

| File | What it is |
|---|---|
| `moveit_server.py`, `moveit_connection.py` | MoveIt 2 in the ROS environment, and the pipe to it |
| `push_motions.py` | one push as four MoveIt motions, and the settings a solution chooses for it |

**`examining`** is the contract and the marks. It is what makes the examiner an examiner rather
than only a simulator: it decides what a solution may see and do, and how its table is judged.

| File | What it is |
|---|---|
| `one_table_cell.py` | one table: the arm, MoveIt and the camera put together, the two viewing poses, and the count of glasses that can be picked |
| `solution_contract.py` | what passes between a solution and the examiner: the arm, the camera, the run |
| `solution_catalogue.py` | every solution by the name the tools know it by, and how a new one is built from that name |
| `table_examiner.py` | the examiner: the arm behind the contract, the clock, the marks, and the list of tables |
| `table_scoring.py` | how a table is marked, by the glasses that can be picked when the solution stops |

**`tools`** are the programs that use the examiner to score and record the solutions. They are
the one package that also uses the shared code, because they run the solutions. The ceiling is
here too, because it is not a solution: it tries pushes in the physics before it makes one,
which only the examiner can do.

A tool that needs to see more than the final result, such as a film or a record, watches the
table through one of two small watcher classes. A physics-step watcher is told after every step
of the physics, which is how a film takes its frames. A push watcher is told before and after
every push, which is how a record keeps each push. A watcher can only look, so it cannot change
what happens on the table, and a solution never sees one.

| File | What it is |
|---|---|
| `evaluate_solution.py`, `compare_results.py` | scoring a solution on the held-out tables, and setting results side by side with a spread |
| `record_runs_per_table.py` | every solution on the same 25 held-out tables, kept table by table |
| `film_solution.py` | films of a solution clearing tables |
| `ceiling_search.py` | the ceiling: a search that may try every push in the physics first |

Four folders hold what these packages read and write, rather than code: `ros/` is MoveIt's
environment and settings, `generated/` is what is made for it at start-up, `results/` is what
every scoring run wrote, and [`runs/`](runs/results.md) keeps one folder per table, with where
the glasses started and what each solution did there.

## The held-out tables

Tables numbered from 10,000 up are the measurement, and nothing is built, chosen or tuned on
them. The fifty used here are 10,000 to 10,049. Every number from `evaluate_solution.py` is for those
tables unless it says `--first` something else. Tuning was done on tables 2,000 to 2,023 and
nowhere else.

## Running it

Every command runs from the problem folder, one level up, because a command often needs both
this folder and a solution's folder. `make help` lists them all.

```
make ros                                      # the ROS environment MoveIt runs in, once
make evaluate-world-model TABLES=50           # score one solution on the held-out tables
make runs                                     # every solution, table by table, in runs/
make test                                     # the quick checks
```
