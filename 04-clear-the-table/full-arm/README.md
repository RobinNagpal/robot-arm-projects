# Problem 4 with the whole arm

The same problem as the first cell's solutions in the numbered folders of `04-clear-the-table`, with
one change: the hand is on the end of a UR5e. A UR5e stands at the table in MuJoCo, **MoveIt 2 plans every motion it makes**, and the
learned part of each solution decides what to *ask* MoveIt for. The documents are in
[`docs/`](../docs/README.md); start with
its README. This page is for the code.

## The four jobs

| | Job | Who does it | Where |
|---|---|---|---|
| 0 | Find a box round each glass, so MoveIt can plan round it | a network that reads the wrist picture | [`seeing.py`](seeing.py) |
| 1 | Decide which glass to move and where it should go | the solution's learned model | `imitation.py`, `world_model.py`, `reinforcement.py`, `vla.py` |
| 2 | Choose the settings handed to MoveIt so that the glass does not tip | the same learned model | the same files |
| 3 | Move the arm | **MoveIt 2**, nothing else | [`pusher.py`](pusher.py), [`moveit_server.py`](moveit_server.py) |

Jobs 1 and 2 are one answer, because on each turn a solution chooses a single push: *this glass, this
way, this far, with these six settings*. The six are the ones MoveIt itself is given (`pusher.Settings`).
The solution never writes a joint angle.

## What a solution is given

A solution is handed a **run** and nothing else: an arm with a wrist camera, and a clock. It decides
when and where to look, which push to ask for, and when the table is finished
([`arm_contract.py`](arm_contract.py)). The **examiner** ([`arm_examiner.py`](arm_examiner.py)) is the other
side: it builds the table, keeps its number to itself, charges the arm time, ends the run when a glass
goes over or the time runs out, and marks the table. The turn-by-turn loop the solutions share, and
their two ways of looking, are in [`solving.py`](solving.py).

## The jaw-only solutions, on the arm

The five solutions of the first cell, in the numbered folders of `04-clear-the-table`, were written
for a jaw that moves with no arm behind it. They answer with a path of waypoints for the jaw rather
than with a push. [`jaw_solutions.py`](jaw_solutions.py) runs them on this arm unchanged, with their
own trained weights. It gives each one the look it was written for, with every glass keeping its
number from one look to the next, and it hands each path to the arm, which MoveIt carries out as a
line of straight motions, all planned before the arm moves. The glasses in a look come from the
box model at the two viewing poses, because those are the only poses it can read. The file's own
docstring says what is the same as in the first cell and what is not.

The two of them that read pictures, imitation and SmolVLA, see the arm camera's pictures, which are
not the pictures they were trained on, so they are expected to do badly until they are trained
again. Solution 3's fitted policy is not kept in git, and it has to be fitted again in its own
folder before it can run here.

## What runs where

MoveIt needs a ROS environment, and the physics and the learning need problem 4's. So MoveIt runs in the
ROS environment kept in [`ros/`](ros/README.md), as a small server ([`moveit_server.py`](moveit_server.py)),
and everything else talks to it over a pipe ([`moveit_link.py`](moveit_link.py)), one JSON line each way.
What crosses is a goal pose and some settings in, and a list of joint angles with times out. `pixi install`
in `ros/` makes the ROS environment once, and after that `pixi run` in this folder's parent is all that is
needed; nothing has to be activated by hand.

## What is in this folder

| File | What it is |
|---|---|
| [`arm_model.py`](arm_model.py) | the UR5e as a MuJoCo model, read out of the same URDF MoveIt plans on |
| [`arm_simulator.py`](arm_simulator.py) | the table and the arm, joint servos, following a joint trajectory |
| [`arm_camera.py`](arm_camera.py) | the wrist camera, moved off the hand's axis |
| [`moveit_server.py`](moveit_server.py), [`moveit_link.py`](moveit_link.py) | MoveIt 2, and the pipe to it |
| [`ros/`](ros/README.md) | the ROS environment MoveIt runs in, the arm's description and MoveIt's settings |
| [`pusher.py`](pusher.py) | one push as four MoveIt motions |
| [`arm_contract.py`](arm_contract.py) | what passes between a solution and the examiner: the arm, the camera, the run |
| [`arm_examiner.py`](arm_examiner.py) | the examiner: the simulated arm behind the contract, the clock, the marks, and the list of tables |
| [`solving.py`](solving.py) | the turn-by-turn loop the solutions share, and how each one chooses to look |
| [`cell.py`](cell.py) | one table: the arm, MoveIt and the camera put together, and the two viewing poses |
| [`seeing.py`](seeing.py), [`build_box_data.py`](build_box_data.py), [`train_box_net.py`](train_box_net.py) | job 0 |
| [`features.py`](features.py), [`nets.py`](nets.py) | how a table and a push are written for the learned models |
| [`collect_pushes.py`](collect_pushes.py) | pushes made at random, informed, or chosen by a model, and what happened |
| [`geometry.py`](geometry.py) | the reference: problem 3's rules choose, fixed settings go to MoveIt |
| [`imitation.py`](imitation.py), [`world_model.py`](world_model.py), [`reinforcement.py`](reinforcement.py), [`vla.py`](vla.py) | solutions 3, 4, 5 and 6 |
| [`jaw_solutions.py`](jaw_solutions.py) | the first cell's five solutions, run on this arm |
| [`checked.py`](checked.py) | the safety check: the world model rejects another solution's risky push |
| [`oracle.py`](oracle.py) | the ceiling: a search that may try every push in the physics first |
| [`teach.py`](teach.py) | the ceiling run on training tables, writing lessons for imitation to copy |
| [`evaluate.py`](evaluate.py), [`report.py`](report.py) | scoring a solution on the held-out tables, and setting results side by side with a spread |
| [`film_arm.py`](film_arm.py) | films of a solution clearing tables |
| [`record_runs.py`](record_runs.py) | every solution on the same 25 held-out tables, kept table by table |
| `results/` | what every run wrote, as JSON |
| [`runs/`](runs/results.md) | one folder per table: where the glasses started, and each solution's result and every push it asked for, as JSON and a picture |
| `weights/` | the box model and the small policies; the large correction to SmolVLA is made again by `make vla` |
| `data/` | the pushes (`*.jsonl`) and, left out of git, the pictures |

## The held-out tables

Tables numbered from 10,000 up are the measurement and nothing is built, chosen or tuned on them. The
fifty used here are 10,000 to 10,049, the same fifty the first cell's solutions are measured on. Every
number from `evaluate.py` is for those tables unless it says `--first` something else. Tuning was done on tables 2,000 to 2,023 and nowhere else.

## Running it

```
make ros                                      # the ROS environment MoveIt runs in, once
make box-data box-net                         # job 0
make collect                                  # push at random with the arm
make imitation world-model                    # solutions 3 and 4
make reinforcement                            # solution 5
make vla-data vla                             # solution 6
make evaluate-world-model TABLES=50           # score one
make evaluate-jaw JAW=geometry-ranked         # score one of the first cell's solutions, on the arm
make runs                                     # every solution, table by table, in runs/
```

`make test` runs the checks that need neither MoveIt nor the physics engine.
