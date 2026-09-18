# CLAUDE.md

## What this repo is

Blocks shaped as triangles, squares, rectangles, rhombuses, pentagons,
hexagons and octagons lie on a table in Gazebo. The work so far is the
dataset: a generator that renders labelled pictures of them with domain
randomization, for training a YOLO model to find and name each block. The
training code is in `training/` and has been checked with short runs. A geometry
baseline and the arm come next.

Read [`README.md`](README.md) first, then
[`docs/yolo-classification/dataset.md`](docs/yolo-classification/dataset.md) for how a picture is
made and why each range is what it is. [`docs/yolo-classification/training.md`](docs/yolo-classification/training.md)
covers the model and its settings, and [`docs/yolo-classification/results.md`](docs/yolo-classification/results.md)
how to read what a run writes.

A second task, finding each block's centre of mass, lives in
`center_of_mass/` and reuses `synthetic/` to render. Its dataset is in
[`docs/center-of-mass/dataset.md`](docs/center-of-mass/dataset.md) and its
model in [`docs/center-of-mass/training.md`](docs/center-of-mass/training.md),
with the first run's scores in
[`docs/center-of-mass/results.md`](docs/center-of-mass/results.md).
The rules below are for the classification task.

This folder is a project on its own. It shares nothing with any other folder:
its own environment, its own code. It must not import from another folder or
point at one.

## Before changing anything

`make test` runs the tests that need no simulator. They cover the class
definitions, the scene drawing and the mask-to-label step, which is where
the logic is.

`make split SPLIT=train COUNT=40 DATA=/tmp/check` and then
`pixi run python -m synthetic.preview --data /tmp/check --output /tmp/check.jpg`
renders a few pictures and draws their labels on them. Nothing about the
generator is verified until you have looked at that sheet: a label that has
drifted off its block passes every test.

Kill leftover `gz sim` processes if a run was interrupted. The generator
starts its own server in its own `GZ_PARTITION`, so it does not collide with
a simulator from another project, but a stale server still holds memory and
GPU.

## The rules that matter

- **Every label comes from the segmentation camera's mask.** Never work a
  label out from where a block was placed. The mask already accounts for
  occlusion, the frame edge and the renderer's own projection, and the
  geometry would have to get all three exactly right.
- **A picture is kept only once the scene has settled** (`take_picture` in
  `gazebo.py`). Gazebo applies changes a render late, so taking the first
  frame after a change mislabels about one picture in five.
- **Every range lives in `Ranges` in `randomization.py`**, and nowhere else.
  A new thing to randomize gets a field there, a row in
  `docs/yolo-classification/dataset.md`, and a reason.
- **`UNSEEN` must stay unseen.** Anything added to it must be outside the
  training ranges, and `test_the_unseen_set_really_is_unseen` checks the
  ones that can be checked.
- **Class definitions keep their gaps.** A change to `shapes.py` must not let
  two classes produce outlines that look the same.
- **Training augmentation must not undo the data's rules.** No hue shift, so
  `UNSEEN` hues stay unseen; no shear or perspective, so class gaps stay.
  `tests/test_training_settings.py` checks both. Settings live in
  `training/settings.py`, with a row in `docs/yolo-classification/training.md`.
- `shapes.py`, `randomization.py` and `labels.py` must not import Gazebo. That
  is what lets the tests run them directly.

## Writing style

Simple English, short sentences, no filler. Comment the *why*, not the *what*.
A comment that restates the line below it is noise. The conceptual background
belongs in the docs, not in the code.

Same for docs: plain English, pinpoint details, no marketing. Doc file names
follow the repo's rule: lowercase words joined by hyphens. Python files use
underscores.
