# CLAUDE.md

## What this project is

A UR5e in MuJoCo picks up an irregular block and places it on a target. A
scripted expert records demonstrations, and an ACT policy from LeRobot
learns the movement from them. The block is found with geometry from an
overhead depth camera, not with a model.

Read [`README.md`](README.md) first, then
[`docs/approach.md`](docs/approach.md) for why each part is built the way
it is. [`docs/results.md`](docs/results.md) has the training results.

This folder is a project of its own. It shares nothing with any other
folder: its own environment, its own code. It must not import from another
folder or point at one. Every dependency is in `pixi.toml` and installs
into `.pixi/`; the robot models download into `assets/` with `make assets`.

## Before changing anything

`make test` runs every test in about 5 seconds, simulator included. They
cover the shapes and grasps, how accurately the camera finds the block,
the inverse kinematics, that the expert succeeds, and the Gazebo files and
conversions (no Gazebo server needed).

`make gazebo RUN=1 DRIVER=expert GUI=0` checks the Gazebo port in about a
minute.

`make view` films the expert and draws the located outline over the true
one. Look at them after any change to the scene, the expert or the
locating: an expert that succeeds by knocking the block onto the target
passes every test.

## The rules that matter

- **The expert only uses what the policy is shown.** It plans from
  `environment_state` and the arm's own joint angles. It never reads the
  simulator's block pose. If the expert needs something new, it goes into
  `environment_state` first, so the policy gets it too.
- **Locating uses only the depth picture and the camera's pose.**
  `locate.py` must not read the block's pose from the simulator. The tests
  compare its answer to the simulator; the code must not.
- **Only successful demonstrations are recorded.** `record.py` plays each
  episode out and keeps it only if the block landed on the target.
- **Evaluation seeds stay unseen.** Recording counts up from seed 0,
  evaluation starts at `FIRST_UNSEEN_SEED` (1,000,000). Keep them apart.
- **Every range lives in `settings.py`** (or, for outline shape, at the top
  of `shapes.py`), with a line in `docs/approach.md` saying why.
- **A change to what the policy sees or does invalidates old runs.** A
  change to `STATE_NAMES`, `ENVIRONMENT_NAMES`, `ACTION_NAMES`, `FPS`, or
  what those numbers mean, needs `make record` and `make train` again.
- **The Gazebo port copies MuJoCo; it does not get its own numbers.** The
  arm's links, joints and controller gains in `gazebo/models.py` are read
  from the MuJoCo model, and the gripper's measurements are MuJoCo's
  Robotiq's. A change to the MuJoCo scene or to what the policy sees must be
  carried over, and `make gazebo-all DRIVER=expert` must still put all ten
  on target before any policy result in Gazebo means anything.
- **Gazebo is stepped in lockstep, never left running.** `gazebo/sim.py`
  sends step requests without waiting for replies (Gazebo loses some) and
  waits on the joint states' timestamps. Do not add retries on the reply:
  that steps the world twice.
- **Do not bring PyPI and conda-forge copies of OpenMP together.** Gazebo
  pulls NumPy from conda-forge; `pixi.toml` pins its BLAS to the OpenBLAS
  build without OpenMP. Without that, importing PyTorch alongside aborts.
- **LeRobot is pinned.** Its dataset and policy APIs change between minor
  versions. Upgrading it means checking `record.py` and `evaluate.py`
  against the new version.

## Writing style

Simple English, short sentences, no filler. Comment the *why*, not the *what*.
A comment that restates the line below it is noise. The conceptual background
belongs in the docs, not in the code.

Same for docs: plain English, pinpoint details, no marketing. Doc file names
follow the repo's rule: lowercase words joined by hyphens. Python files use
underscores.
