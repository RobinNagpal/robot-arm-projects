# v3: turn the table top flat

This folder is plans and one calculation. There is no robot code in it yet.

## The setup

The room is the same as in v2: a UR5e arm standing on the floor, with a
camera on its wrist and a two-finger gripper; four table legs; and one table
top, a thin board.

One thing is different. **The table top starts standing upright, between two
holders.** It stands on one long edge, and each of its two ends sits in the
slot of a holder. The holders are heavy, or bolted down, so they never move,
and between them the top cannot tip over or slide sideways. The only way it
can come out is straight up.

That makes the start simple, on purpose. The arm grips the middle of the top's
upper edge and lifts it straight up out of the holders. It is then hanging
straight down from the fingers, and the real question begins: how to get it
from hanging to flat, and onto the four legs.

For comparison, v2 as it is today starts the top lying flat on two stands, so
it never has to turn it at all.

The rule from v2 still holds. The robot is told nothing about the room. It
knows only itself: where its base is and how its gripper and camera are
built. Everything else, including how heavy the top is, it has to measure.

## The plan, in two parts

**Part 1 — the 90° turn: one joint, or many? This is what v3 is working on
now.**

The top has to turn 90 degrees, from hanging to flat. The arm can do that by
turning a single joint, wrist 1, and holding all the others still. Or it can
move several joints together, so that one chosen point of the board — the
gripped edge, or the board's middle — stays still while the board turns about
it. Part 1 works out what that choice does to the arm: the torque on every
joint, how fast each one has to turn, and what a joint's real limits mean for
which way to go. → [`one-joint-or-many.md`](one-joint-or-many.md)

**Part 2 — onto the legs, two first. Next, not started.**

Rather than turn the top flat in the air and set it down on all four legs at
once, the arm rests the top's lower edge on the two far legs first. Then it
turns the top down about that edge, moving the arm as it goes, until the top
touches and settles on all four legs. It is how a person puts a heavy top on
a table. → [`tilt-onto-legs.md`](tilt-onto-legs.md)

Both parts sit inside the whole job — look round, measure, stand the legs,
pick the top up, put it down, check the table — which
[`pick-up-and-place.md`](pick-up-and-place.md) plans from start to finish,
along with the other ways the top could be turned.

## What each file answers

| File | Question |
| --- | --- |
| [`one-joint-or-many.md`](one-joint-or-many.md) | **Part 1.** To turn the top 90°, is it harder on the arm to turn one joint or several? Worked out joint by joint on v2's robot. What real limits does a joint have, and which way do they push the design? How heavy a top can the turn take, and how is weight set in Gazebo? |
| [`tilt-onto-legs.md`](tilt-onto-legs.md) | **Part 2.** Resting the top on two legs first, then tilting it down onto four: how it works, and what can go wrong — mostly, legs being knocked over. |
| [`pick-up-and-place.md`](pick-up-and-place.md) | The whole job, from the holders to the finished table. The ways the top could be turned, one of them in full detail, with pseudo code, the libraries and the gripper. |

## The short answers

**Part 1.** Turning with one joint or with several makes almost no difference
to the torque on any joint. Nearly all of a joint's torque is what it takes
just to hold things up, and that depends on where things are, not on which
joints put them there. Turning one joint is also the quicker of the two,
because the other way makes the busiest joint turn further. What does make a
difference is the arm's *posture*: starting the turn with the wrist flipped
takes 28% off the joint that works hardest.

**Why part 2 exists.** For a turn in the air, it is the grip that gives out
first, not a joint: held flat by one edge, a top heavier than about 0.8 kg
twists out of v2's fingers. Resting the top on the legs before it goes flat
means it is never held flat in the air at all, so much heavier tops become
possible — at the price of having to turn it without knocking a leg over.

## The pictures

The pictures are in [`figures/`](figures). Each script there draws the
pictures for one file:

| Script | Draws the pictures for |
| --- | --- |
| `figures/pick_up_and_place.py` | `pick-up-and-place.md` (and holds the drawing helpers the other two use) |
| `figures/one_joint_or_many.py` | `one-joint-or-many.md` |
| `figures/tilt_onto_legs.py` | `tilt-onto-legs.md` |
| `figures/joint_torques.py` | the torque charts in `one-joint-or-many.md`, section 2 |

To redraw them, use any Python with matplotlib and numpy. v2's environment
has both:

```
cd v3-turn-top-flat/figures
../../v2-assemble-table/.pixi/envs/default/bin/python pick_up_and_place.py
../../v2-assemble-table/.pixi/envs/default/bin/python one_joint_or_many.py
../../v2-assemble-table/.pixi/envs/default/bin/python tilt_onto_legs.py
```

They are sketches to explain the idea, not drawings to scale. The charts use
v2's real numbers.

`joint_torques.py` is different: it is a calculation, not a sketch. It loads
v2's robot from `figures/ur5e_v2_gripper.urdf` and needs PyBullet, which v2's
environment also has. It checks itself before printing anything, and takes
about a minute and a half:

```
cd v3-turn-top-flat/figures
../../v2-assemble-table/.pixi/envs/default/bin/python joint_torques.py
```
