# Running the trained policy in Gazebo

The policy was trained entirely in MuJoCo. This part rebuilds the same room
in Gazebo Harmonic, the simulator v1 to v4 use, and runs the same trained
policy there, with no retraining and no changes. The camera finds the block
the same way, and the model drives the arm the same way.

It answers a different question from `make evaluate`. That one asks how
well the policy does in the simulator it learned in. This one asks how much
of what it learned survives a change of simulator: different physics,
different contacts, different joint controllers, and a different gripper.
That is a small preview of what moving to a real arm would ask.

## Running it

```
make gazebo RUN=3                  # run 3, in Gazebo's window, in real time
make gazebo RUN=3 GUI=0            # the same with no window: faster, prints the outcome
make gazebo-all                    # all 10 runs, no window, then a table of outcomes
make gazebo RUN=3 DRIVER=expert    # the scripted expert instead of the policy
```

`POLICY=...` picks another checkpoint, as with `make evaluate`.

**What to expect.** Gazebo takes 30 to 40 seconds to load the first time,
while it compiles its shaders, and a few seconds after that. Each run then
takes about 16 seconds, the time the policy is given, as in MuJoCo. With
the window, it waits 8 seconds for the window to show the scene before
anything moves, and holds the end for 3 seconds.

**What the window shows:**

- the 3D view, looking at the table from the front right. Drag to turn it,
  scroll to zoom;
- **the overhead camera** as a dark box 1 m above the table, with its blue
  lens facing down. That is the camera the block is found with;
- a panel with **that camera's live picture**, what the geometry sees;
- the simulation clock.

The window has no play or pause buttons, on purpose: the world is stepped
from Python, in lockstep with the policy, and pressing play would let it
run on its own.

## The ten runs

Each run is one block and one target: the first ten episodes of the MuJoCo
evaluation, seeds 1,000,000 to 1,000,009. None was in the training data,
and because they are the same episodes, `make evaluate` shows what the
policy did on each one in MuJoCo, to compare.

| Run | Seed | Sides | Widest | Thick | Block starts at, turned | Target at |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,000,000 | 3 | 10.9 cm | 2.6 cm | (0.46, 0.12) m, turned −72° | (0.45, −0.13) m |
| 2 | 1,000,001 | 4 | 8.7 cm | 2.8 cm | (0.52, 0.29) m, turned 40° | (0.57, −0.15) m |
| 3 | 1,000,002 | 3 | 10.5 cm | 3.9 cm | (0.56, 0.17) m, turned −104° | (0.42, −0.18) m |
| 4 | 1,000,003 | 5 | 9.6 cm | 3.2 cm | (0.48, 0.27) m, turned −56° | (0.54, −0.10) m |
| 5 | 1,000,004 | 6 | 7.8 cm | 3.6 cm | (0.40, 0.14) m, turned −112° | (0.52, −0.15) m |
| 6 | 1,000,005 | 5 | 7.3 cm | 3.4 cm | (0.57, 0.19) m, turned 121° | (0.52, −0.10) m |
| 7 | 1,000,006 | 5 | 9.8 cm | 2.5 cm | (0.55, 0.23) m, turned 46° | (0.43, −0.30) m |
| 8 | 1,000,007 | 3 | 11.0 cm | 2.5 cm | (0.43, 0.24) m, turned 35° | (0.56, −0.14) m |
| 9 | 1,000,008 | 5 | 9.4 cm | 3.1 cm | (0.45, 0.24) m, turned 148° | (0.48, −0.11) m |
| 10 | 1,000,009 | 4 | 9.9 cm | 3.9 cm | (0.53, 0.14) m, turned 81° | (0.53, −0.24) m |

Positions are from the arm's base: x away from it, y to its left. The block
starts on the left and the target is on the right.

Each run's world is written to `data/gazebo/run-N/`: `world.sdf` and the
block's mesh, `block.obj`. They can be opened in Gazebo on their own with
`pixi run gz sim data/gazebo/run-3/world.sdf`, to look at a run's scene
without anything moving.

**How each run is scored**, the same as in MuJoCo, with the outcome named:

| Outcome | Meaning |
| --- | --- |
| on target | centre of mass within 15 mm of the target, block flat, gripper open |
| placed off | carried and put down flat, but more than 15 mm off |
| never lifted | the block never rose 2 cm off the table |
| tipped | put down, but not lying flat |
| still holding | the gripper had not let go when time ran out |

## What is the same as in MuJoCo

- **The arm.** The Gazebo model is written from the MuJoCo one
  ([`gazebo/models.py`](../pick_place/gazebo/models.py)): every link's
  position, mass and inertia, every joint's axis and range, the same meshes
  and collision shapes. So the joint angles mean the same thing in both.
- **The arm's controllers.** Each joint gets MuJoCo's stiffness, damping and
  force limit, and the arm's links ignore gravity, as MuJoCo's gravity
  compensation makes them. MuJoCo's motor inertia ("armature"), which SDF
  cannot express, is added to the links' own inertia instead.
- **The camera.** The same place, 1 m above the table looking straight down,
  the same field of view and resolution. Its depth picture goes through the
  same geometry code ([`locate.py`](../pick_place/locate.py)).
- **What the policy is shown and what it sends back.** The Gazebo episode
  ([`gazebo/env.py`](../pick_place/gazebo/env.py)) gives exactly the same
  15 numbers and takes the same 7. At the start of run 1 the numbers from
  both simulators agree to the millimetre.
- **The control loop.** 20 steps a second, each one: read, ask the policy,
  send, step the world 50 ms. Gazebo is paused between steps, so however
  fast or slow the computer is, the policy sees the same timing.
- **The block and target.** The same outline, thickness, mass, start and
  target as the MuJoCo episode with the same seed.

## What is different

These are what the test is about. The policy never saw any of them.

- **The physics engine.** Gazebo uses DART, not MuJoCo. Contacts, friction
  and how a gripped block settles all behave differently.
- **The gripper.** The Robotiq 2F-85 is a closed four-bar linkage on each
  side. MuJoCo holds it together with constraints; Gazebo's physics does not
  handle closed chains well. So Gazebo has a plain two-finger parallel
  gripper with the Robotiq's measurements: pads 22 mm wide and 37.5 mm
  tall, opening to 85 mm, the point between the fingertips in the same place
  on the wrist. Its fingers move straight, where the Robotiq's swing on an
  arc. How closed it is gets reported on the Robotiq's scale, from a table of
  the Robotiq's gap at each reading, measured in MuJoCo.
- **The controllers' damping.** MuJoCo's actuator damps the joint's speed.
  Gazebo's controller damps how fast the error changes. The two agree while
  the target holds still. Each time the target moves, 20 times a second,
  Gazebo's adds a short push towards it, capped at the force limit for one
  physics step.
- **The arm starts in its home pose by construction.** Gazebo 8 cannot start
  a joint at a chosen angle, so the arm is built in the home pose and each
  joint's zero is the home angle. The driver converts in both directions.
  This changes nothing the policy sees.

## Checking the port before trusting it

A policy failing in Gazebo means something only if Gazebo itself is right.
So the **scripted expert**, which plans from the same numbers and does not
learn anything, was run on all ten runs first:

```
make gazebo-all DRIVER=expert
```

It put the block on the target in **10 of 10** runs, 0.4 mm off on median,
as it does in MuJoCo. The arm reaches where it is sent, the gripper holds,
the camera finds the block (0.6 mm from Gazebo's own record in run 1), and
the scoring works. What the policy then does in Gazebo is down to the
policy.

## The policy's results

**Not run yet.** `make gazebo-all` runs the policy on all ten and prints a
table; its results go here, next to what the same policy did on the same
ten episodes in MuJoCo (`make evaluate`, the first ten lines).

One run has been done, only to check the policy works end to end in Gazebo:
on run 1 it picked the block up, carried it across and set it down flat,
**15.2 mm** from the target, just outside the 15 mm the success check allows.

## Troubleshooting

- **It sits at "starting Gazebo..." for up to a minute** the first time:
  Gazebo compiles its shaders. Later starts take a few seconds.
- **To see Gazebo's own messages**, run
  `pixi run python -m pick_place.gazebo.run --run 3 --verbose`. Two errors
  there are harmless:
  `Unable to load Ogre Plugin ... Rendering will not be possible` (it then
  renders fine, as in v4), and `Material file ... .mtl not found` for the
  arm's meshes, which get their colours from the world file instead.
- **A Gazebo left running** after an interrupted run: `pkill -f "gz sim"`.
  Each run uses its own `GZ_PARTITION`, so it never talks to a Gazebo
  started by another project.

## How the Python side talks to Gazebo

The same way as v4, with no ROS: Gazebo runs as its own process, headless,
and Python talks to it over Gazebo's own transport
([`gazebo/sim.py`](../pick_place/gazebo/sim.py)).

| What | Topic or service |
| --- | --- |
| joint angles, read | `/world/pick_place/model/ur5e/joint_state` |
| joint targets, sent | `/ur5e/<joint>/command`, one per joint and finger |
| the depth picture, read | `/overhead/depth` |
| the camera's colour picture, for the window | `/overhead/image` |
| where the block is, for scoring only | `/model/block/pose` |
| step the world | the `/world/pick_place/control` service |

One thing about Gazebo shaped the stepping code. With cameras in the world,
Gazebo carries out every step request but loses some of its replies. A
caller that waits for the reply can wait forever, and one that retries steps
the world twice. So a step request is sent without waiting for the reply,
and the timestamps on the joint readings say when the step is done.

**Two changes to the environment**, both in `pixi.toml`, came with adding
Gazebo. Gazebo's packages bring NumPy from conda-forge, and its default
maths library uses OpenMP, which crashed next to PyTorch's own copy ("OMP:
Error #15"); the OpenBLAS build with plain threads is used instead. And
NumPy is held below 2.3 for LeRobot.
