# Problem 4 with the whole arm

The same problem as the other folders in `04-clear-the-table`, with one change: the hand is on the end
of a UR5e. A UR5e stands at the table in MuJoCo, **MoveIt 2 plans every motion it makes**, and the
learned part of each solution decides what to *ask* MoveIt for. The documents are in
[`docs/04-clear-the-table/full-arm/`](../../docs/04-clear-the-table/README.md); start with
its README. This page is for the code.

## The four jobs

| | Job | Who does it | Where |
|---|---|---|---|
| 0 | Find a box round each glass, so MoveIt can plan round it | a network that reads the wrist picture | [`seeing.py`](seeing.py) |
| 1 | Decide which glass to move and where it should go | the solution's learned model | `imitation.py`, `world_model.py`, `reinforcement.py`, `vla.py` |
| 2 | Choose the settings handed to MoveIt so that the glass does not tip | the same learned model | the same files |
| 3 | Move the arm | **MoveIt 2**, nothing else | [`pusher.py`](pusher.py), [`moveit_server.py`](moveit_server.py) |

Jobs 1 and 2 are one answer, because a solution is asked once per turn and replies with a single push:
*this glass, this way, this far, with these six settings*. The six are the ones MoveIt itself is given
(`pusher.Settings`). The solution never writes a joint angle.

## What runs where

MoveIt needs the ROS environment, and the physics and the learning need problem 4's. So MoveIt runs in the
ROS environment as a small server ([`moveit_server.py`](moveit_server.py)) and everything else talks to it
over a pipe ([`moveit_link.py`](moveit_link.py)), one JSON line each way. What crosses is a goal pose and
some settings in, and a list of joint angles with times out. `pixi run` in this folder's parent is all
that is needed; nothing has to be activated by hand.

## What is in this folder

| File | What it is |
|---|---|
| [`arm_model.py`](arm_model.py) | the UR5e as a MuJoCo model, read out of the same URDF MoveIt plans on |
| [`arm_bench.py`](arm_bench.py) | the table and the arm, joint servos, following a joint trajectory |
| [`arm_camera.py`](arm_camera.py) | the wrist camera, moved off the hand's axis |
| [`moveit_server.py`](moveit_server.py), [`moveit_link.py`](moveit_link.py) | MoveIt 2, and the pipe to it |
| [`pusher.py`](pusher.py) | one push as four MoveIt motions |
| [`cell.py`](cell.py), [`episode.py`](episode.py) | one table, the loop over it, and the queue |
| [`seeing.py`](seeing.py), [`build_box_data.py`](build_box_data.py), [`train_box_net.py`](train_box_net.py) | job 0 |
| [`features.py`](features.py), [`nets.py`](nets.py) | how a table and a push are written for the learned models |
| [`collect_pushes.py`](collect_pushes.py) | pushes made at random, informed, or chosen by a model, and what happened |
| [`geometry.py`](geometry.py) | the reference: problem 3's rules choose, fixed settings go to MoveIt |
| [`imitation.py`](imitation.py), [`world_model.py`](world_model.py), [`reinforcement.py`](reinforcement.py), [`vla.py`](vla.py) | solutions 3, 4, 5 and 6 |
| [`checked.py`](checked.py) | the safety check: the world model rejects another solution's risky push |
| [`oracle.py`](oracle.py) | the ceiling: a search that may try every push in the physics first |
| [`teach.py`](teach.py) | the ceiling run on training tables, writing lessons for imitation to copy |
| [`evaluate.py`](evaluate.py), [`report.py`](report.py) | scoring a solution on the held-out tables, and setting results side by side with a spread |
| [`film_arm.py`](film_arm.py) | films of a solution clearing tables |
| `results/` | what every run wrote, as JSON |
| `weights/` | the box model and the small policies; the large correction to SmolVLA is made again by `make vla` |
| `data/` | the pushes (`*.jsonl`) and, left out of git, the pictures |

## The held-out tables

Tables numbered from 10,000 up are the measurement and nothing is built, chosen or tuned on them. The
fifty used here are 10,000 to 10,049, the same as problem 4's. Every number from `evaluate.py` is for those
tables unless it says `--first` something else. Tuning was done on tables 2,000 to 2,023 and nowhere else.

## Running it

```
make box-data box-net                         # job 0
make collect                                  # push at random with the arm
make imitation world-model                    # solutions 3 and 4
make reinforcement                            # solution 5
make vla-data vla                             # solution 6
make evaluate-world-model TABLES=50           # score one
```

`make test` runs the checks that need neither MoveIt nor the physics engine.
