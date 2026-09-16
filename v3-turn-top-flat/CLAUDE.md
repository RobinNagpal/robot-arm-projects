# CLAUDE.md

## What this repo is

A UR5e in Gazebo finds a table top standing upright between two holders,
measures it, and lifts it straight up out of them. Then one of three things:

- `make wrist` — turns it flat in the air: wrist 1 turns on its own, every
  other joint stays still.
- `make whole-arm` — turns it flat in the air: the whole arm moves so the
  gripped edge stays put and the board turns about it.
- `make tilt` — puts it on the four legs standing where the table goes:
  rests its lower edge on the far two, then tilts it down onto all four, and
  checks the table.

Read [`README.md`](README.md) first. The plans and the calculations behind the two
turns are in [`one-joint-or-many.md`](one-joint-or-many.md),
[`pick-up-and-place.md`](pick-up-and-place.md) and
[`tilt-onto-legs.md`](tilt-onto-legs.md).

This folder is a project on its own. It started as a copy of
`../v2-assemble-table`, but it shares nothing with it or with any other
folder: its own environment, its own ROS packages (`turn_top_flat`,
`turn_top_flat_moveit_config`), its own figures. It must not import from
another folder or point at one.

## Before changing anything

`make test` runs the tests that need no simulator. They cover the room, the
fitting, the reading of a room, and the grip and turn geometry, which is
where most of the logic is.

`make wrist GUI=false`, `make whole-arm GUI=false` and `make tilt GUI=false`
run the whole thing end to end, a few minutes each. Nothing is really
verified until all three have passed.

Kill leftovers between runs. A simulator that was killed rather than shut down
leaves its ROS endpoints registered and the next run will stall on them. If
another project's cell is running at the same time, give this one its own
`ROS_DOMAIN_ID` and `GZ_PARTITION`, or the two talk over each other.

## The one rule that matters

The robot is told nothing about the room. It knows where its own base is and
how its own tooling is built (`arm/dimensions.py`), and it always turns the
top at the same spot in front of it (`TURN_SPOT` in `task.py`), which is its
own choice of where to work. Everything else — the floor height, the top's
size and pose, how heavy it is, where the legs stand and how tall they are —
it measures or does without.

- `world/` is the simulator's side. It decides the sizes and positions of
  everything, and **nothing outside `world/` may import from it.**
  `test_world.py` fails if anything does.
- A new number the robot needs is either a fact about the robot (it goes in
  `arm/dimensions.py`) or a choice about how to do the job (it goes next to
  the code that uses it, with the reason). It is never a fact about the room.

## Where things belong

- `perception/` and `assembly/` must not import ROS. That is what lets the
  tests run them directly, and it is worth keeping.
- `task.py` is the only module that knows what order things happen in. Keep
  sequencing there and capability in the modules it calls.

## Writing style

Simple English, short sentences, no filler. Comment the *why*, not the *what* —
a comment that restates the line below it is noise. The conceptual background
belongs in the docs, not in the code.

Same for docs: plain English, pinpoint details, no marketing. Doc file names
follow the repo's rule: lowercase words joined by hyphens.
