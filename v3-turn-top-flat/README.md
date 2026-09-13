# v3: the table top starts leaning on a wall

This folder is plans only. There is no code in it yet. The working build is
[`../v2-assemble-table`](../v2-assemble-table), where the top starts lying flat on
two stands.

## The problem

The room is the same as in v2:

- a UR5e arm standing on the floor, with a camera on its wrist and a
  two-finger gripper;
- four table legs;
- one table top, a thin board.

One thing changes. **The table top starts leaning against a low wall**, almost
upright. It stands on one long edge on the floor, and leans back 15 to 22
degrees onto the wall's top corner.

The arm has to:

1. find everything with its camera, and measure the top and the legs;
2. work out where the legs go for a top that size;
3. stand the four legs there (as v2 already does);
4. pick the top up off the wall;
5. get it from upright to flat, without dropping it and without knocking a
   leg over;
6. lay it on the legs, and check the table.

Step 5 is the hard part, and it is why v2 starts the top flat on two stands.

The rule from v2 still holds. The robot is told nothing about the room. It
knows only itself: where its base is and how its gripper and camera are
built. Everything else, including how heavy the top is, it has to measure.

## What each file answers

| File | Question |
| --- | --- |
| [`TOP_FROM_WALL.md`](TOP_FROM_WALL.md) | What are the ways to turn the top flat? Way A in detail: grip the upper edge and swing it flat in the air. |
| [`SWING_PHYSICS.md`](SWING_PHYSICS.md) | During that swing, does only the wrist move or the whole arm? Does moving one joint strain the arm more than moving all six — worked out joint by joint on v2's robot? What real limits does a joint have, and which way do they push the design? How heavy a top can it handle, and how is the weight set in Gazebo? |
| [`TILT_ON_LEGS.md`](TILT_ON_LEGS.md) | The way a person would do it: rest one edge on two legs, then tilt the top down. How does it work, and what can go wrong? |

Short answer: the swing is simple but only works for light tops, about
0.8 kg with v2's gripper. Resting on the legs handles tops several times
heavier, but the legs can be knocked over, so it needs much more care.

Swinging with one joint or with the whole arm makes almost no difference to
the torque on any joint, because nearly all of it is the torque needed just to
hold things up, and that depends on where things are, not on which joints put
them there. What does make a difference is the arm's posture: starting with the
wrist flipped takes 28% off the busiest joint.

## The pictures

The pictures are in [`figures/`](figures). Each script there draws the
pictures for one file:

| Script | Draws the pictures for |
| --- | --- |
| `figures/top_from_wall.py` | `TOP_FROM_WALL.md` (and holds the drawing helpers the other two use) |
| `figures/swing_physics.py` | `SWING_PHYSICS.md` |
| `figures/tilt_on_legs.py` | `TILT_ON_LEGS.md` |
| `figures/joint_torques.py` | the torque charts in `SWING_PHYSICS.md`, section 2 |

To redraw them, use any Python with matplotlib and numpy. v2's environment
has both:

```
cd v3-turn-top-flat/figures
../../v2-assemble-table/.pixi/envs/default/bin/python top_from_wall.py
../../v2-assemble-table/.pixi/envs/default/bin/python swing_physics.py
../../v2-assemble-table/.pixi/envs/default/bin/python tilt_on_legs.py
```

They are sketches to explain the idea, not drawings to scale. The two charts
use v2's real numbers.

`joint_torques.py` is different: it is a calculation, not a sketch. It loads
v2's robot from `figures/ur5e_v2_gripper.urdf` and needs PyBullet, which v2's
environment also has. It checks itself before printing anything, and takes
about a minute and a half:

```
cd v3-turn-top-flat/figures
../../v2-assemble-table/.pixi/envs/default/bin/python joint_torques.py
```
