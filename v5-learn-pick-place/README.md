# v5: learn to pick and place

A UR5e arm picks up an irregular block from a random spot on a table and
sets it down on a red target. The movement is learned: a scripted expert
does the job a few hundred times in simulation, every joint angle it
commands is recorded, and an **ACT** policy (Action Chunking with
Transformers) is trained to copy it. The block is found with plain
geometry from an overhead depth camera, with no model.

```
make setup      # install the environment and download the arm and gripper models
make view       # film the scripted expert, and draw what the camera found, into figures/expert/
make record     # record 200 expert demonstrations as a LeRobot dataset, about 40 s
make train      # train ACT on them, about 40 min on an M5 MacBook
make evaluate   # run the best trained policy on 50 episodes it never saw, next to the expert
make gazebo RUN=3   # run the same policy in Gazebo, a simulator it never saw, in Gazebo's window
make test       # the tests, about 5 s
```

Training and evaluation run in MuJoCo, on a Mac or on Linux; the trained
policy can also be run in Gazebo (see [In Gazebo](#in-gazebo)). All dependencies are
installed by pixi into `.pixi/` inside this folder, and the robot models are
downloaded into `assets/`; nothing is installed anywhere else.

## The task

- **The arm:** a UR5e with a Robotiq 2F-85 two-finger gripper, bolted to the
  table. Both are from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie).
- **The block:** a new irregular shape every episode: 3 to 6 sides, no two
  alike, 7 to 12 cm across, 2.5 to 4 cm thick. It starts somewhere in the
  pick zone on the arm's left, turned any way.
- **The target:** a red disc somewhere in the place zone on the arm's right.
- **Success:** the block's centre of mass ends within 15 mm of the target's
  middle, lying flat on the table, with the gripper open.

## How it works

```
overhead depth camera ──► geometry ──► grasp point, place point, grasp direction, thickness
                                                             │
arm joint angles + gripper ──► gap from the fingertips to each goal
                                                             │
                                           ACT ──► how far to move each joint, and the gripper
```

1. **Find the block** ([`locate.py`](pick_place/locate.py)). Every depth
   pixel goes back through the lens model into a point in the room, as in
   v1. The points standing above the table are the block, and its top face's
   outline gives the centre of mass. Error against the simulator: 0.15 mm
   on average.
2. **Choose the grasp** ([`shapes.py`](pick_place/shapes.py)). One finger
   flat on a side of the block, the other closing straight towards it, the
   block no wider than the open fingers, held as close to its centre of
   mass as possible.
3. **Move** ([`evaluate.py`](pick_place/evaluate.py)). Twenty times a
   second, ACT is given the arm's joint angles and the gap from the
   fingertips to the grasp point and to the place point, and answers with how
   far to move each joint. It plans one second ahead and carries out half of
   it before looking again. Why relative and not absolute is in
   [`docs/approach.md`](docs/approach.md#why-relative-not-absolute): the
   absolute version missed the block by 2 to 3 cm.

The training data comes from a scripted expert ([`expert.py`](pick_place/expert.py)):
goals for the fingertips, smooth motion towards each, inverse kinematics to
turn each point into joint angles, and the gripper closing or opening only
once the arm is within 1.5 mm of its goal. In half the recordings the arm is
pushed off course while it travels, so the demonstrations also show how to
get back. It lands the block 0.4 mm from the target on median and misses
about 1 episode in 70; only its successful episodes are recorded.

## The docs, in reading order

1. [`docs/workflow.md`](docs/workflow.md): the whole pipeline start to finish,
   finding the block, recording, training, running the model, scoring it,
   and the three training runs.
2. [`docs/dataset.md`](docs/dataset.md): what is recorded, one real entry
   explained number by number, and one episode walked through.
3. [`docs/approach.md`](docs/approach.md): the reason for every choice, why
   ACT, why MuJoCo, why no model for finding the block, and what was changed
   in the stock robot models.
4. [`docs/results.md`](docs/results.md): the scores, where the failures go,
   and what to try next.
5. [`docs/gazebo.md`](docs/gazebo.md): running the trained policy in Gazebo,
   the ten fixed runs, and what is the same and what differs from MuJoCo.

## What is recorded

One row per control step, 20 per second, about 175 per episode, in
LeRobot's dataset format under `data/pick-place/`:

| Field | Size | What |
| --- | --- | --- |
| `observation.state` | 7 | the six joint angles and how closed the gripper is |
| `observation.environment_state` | 8 | fingertips to grasp point (x, y, z), fingertips to place point (x, y, z), wrist turn left to line up, block thickness |
| `action` | 7 | how far to move each of the six joints, and the gripper: 0 open, 1 closed |

## Results

**The best policy puts the block on the target in 37 of 50 episodes it never
saw (74%), 8.1 mm off on median.** The expert it learned from scores 49 of
50, 0.4 mm off. The failures are all about precision where the gripper
closes or opens, never about the order of the task.

That is the checkpoint at 15,000 steps, not the last one: later checkpoints
scored lower. [`docs/results.md`](docs/results.md) has the three training
runs, what each one showed, and what to try next.

`make evaluate` uses that checkpoint by default.

## In Gazebo

The trained policy also runs in Gazebo Harmonic, the simulator v1 to v4 use,
with no retraining. The arm, camera, block and target are rebuilt there from
the MuJoCo model, and there are ten fixed runs, each with its own block and
target:

```
make gazebo RUN=3          # one run, in Gazebo's window, with the overhead camera's picture beside it
make gazebo-all            # all ten, no window, then a table of outcomes
make gazebo RUN=3 DRIVER=expert   # the scripted expert instead: 10 of 10 on target
```

[`docs/gazebo.md`](docs/gazebo.md) has the runs, what differs from MuJoCo
(the physics engine and the gripper, mainly), and how the port was checked.

## Running more

```
make record EPISODES=500                      # more demonstrations
make train NAME=act-500 STEPS=40000           # a longer run, under its own name
make evaluate NAME=act-500 EVAL_EPISODES=100  # score it
make view SEEDS="3 4 5"                       # film other episodes
make doctor                                   # versions of everything
```

Checkpoints are saved every 5,000 steps under
`outputs/NAME/checkpoints/`; `POLICY=outputs/act/checkpoints/010000/pretrained_model`
evaluates another one. `make train` deletes the previous run of the same
`NAME`, so give a new run its own name to keep the current best.

**The torchcodec warnings.** Training prints a long list of `Could not load
this library ... libtorchcodec` errors when it starts. They are harmless:
LeRobot tries its video decoder, finds no FFmpeg, and falls back. This
dataset has no video in it.

## Layout

```
pick_place/
  settings.py     every number: zones, block ranges, camera, rates
  scene.py        builds the MuJoCo model for one episode
  shapes.py       irregular outlines and where the fingers can hold one
  locate.py       depth picture to block outline, centre of mass and grasp
  kinematics.py   joint angles for a fingertip position
  env.py          one episode: what the policy sees, and whether it worked
  expert.py       the scripted demonstrations
  record.py       expert episodes into a LeRobot dataset
  evaluate.py     trained policy against the expert, on unseen episodes
  view.py         film the expert, draw what the camera found
  video.py        films an episode
  gazebo/
    models.py     the Gazebo world as SDF, the arm built from the MuJoCo model
    sim.py        starts Gazebo, steps it, reads and commands the arm
    env.py        one episode in Gazebo, with the same interface as env.py
    run.py        the ten runs, with the policy or the expert
tests/
docs/
```

## What comes next

1. **Record the Gazebo results** in `docs/gazebo.md` once `make gazebo-all`
   has been run.
2. **Diffusion Policy** on the same data, and compare it to ACT.
3. **The wrist camera** as an input, so the last few centimetres of the
   grasp are guided by what the gripper sees.
4. **More demonstrations**, and keeping the best checkpoint automatically.
5. **Stacking**: the target becomes the top of another block, and then the
   order of several irregular blocks, as discussed for this project.
