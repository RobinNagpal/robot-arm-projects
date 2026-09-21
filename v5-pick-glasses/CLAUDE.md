# CLAUDE.md

## What this repo is

One task, done properly: a UR5e in Gazebo measures each drinking glass on a
table, picks it up, turns it over and stands it on a drying rack. Read
[`README.md`](README.md) first, then [`pseudocode.md`](pseudocode.md) for what
every file and function is for, [`architecture.md`](architecture.md) for the
layout, and [`implementation-notes.md`](implementation-notes.md) for why it is
built the way it is.

## The rule that governs everything

**No glass's size appears anywhere in this project.** Not in a constant, not in
a test fixture, not in a mesh file shipped with the repo. The arm measures
every glass during the run.

What the project may hold is *rules and limits*: fractions of a glass's own
height, and numbers belonging to the gripper. "Hold the narrowest part below
the bowl" belongs here. "Hold it 90 mm up" does not — that is true of exactly
one glass.

If you find yourself wanting to write a glass measurement down, the design has
gone wrong somewhere above. The usual cause is a rule that does not generalise,
and the fix is to change the rule, not to special-case the glass.

## Before changing anything

`make test` runs the tests that need no simulator. They cover the shapes, the
profile arithmetic, the grip rules, the force sums and the rack geometry, which
is where nearly all the logic is.

Tests here run against **families of glasses, not single examples**. A rule
that works on one wine glass and fails on a differently proportioned one is the
exact failure this project exists to prevent, and a single test glass cannot
catch it. `family(kind, count, seed)` in `glasses/shapes.py` draws forty of
them across the plausible range; use it.

`make run GUI=false` runs the whole thing end to end. Nothing is really
verified until this has passed.

Kill leftovers between runs. A simulator that was killed rather than shut down
leaves its ROS endpoints registered and the next run will stall on them.

## Where things belong

One folder per thing in the room. Everything about the arm is in `arm/`, and
the same for `table/`, `glasses/`, `rack/` and `world/` — the model the
simulator loads, the settings, and the code, together. A new file goes with its
subject, not with other files of its type.

- Numbers live with their subject, and nowhere else: the table in
  `table/layout.py`, the arm's reach and working heights in
  `arm/dimensions.py`, the rack and its tilt budget in `rack/layout.py`, the
  grip rules in `glasses/spec.py`.
- `glasses/` must not import ROS — not `profile.py`, `rules.py`, `spec.py`,
  `perception.py`, `force.py`, `detect.py`, `shapes.py` or `spawn.py`. That is
  what lets the tests run them directly on drawn masks and drawn outlines, and
  it is worth keeping.
- `task.py` is the only module that knows what order things happen in. Keep
  sequencing there and capability in the modules it calls.

## Two things that are easy to get wrong here

**A refused glass is a result, not a failure.** Broken glass leaves shards and
an arm that will carry on moving through them, so anything doubtful ends with
the glass back on the table and a line in the report. Do not add a fallback
that has the arm try anyway.

**Every measurement carries error, so the last millimetres are felt, not
driven.** The fingers close until they touch and then check the width; the
glass comes down until the rim touches and then checks the weight transferred.
A step that computes a height and drives to it is a step that will chip a rim
the day a measurement is 2 mm out.

## Writing style

Simple English, short sentences, no filler. Comment the *why*, not the *what* —
a comment that restates the line below it is noise. The conceptual background
belongs in the docs, not in the code.

Same for docs: plain English, pinpoint details, no marketing.
