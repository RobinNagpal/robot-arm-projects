# v3: turn the table top flat

A robot arm finds a table top standing upright between two holders and
lifts it straight up out of them. Then it either turns it flat in the air, in
one of two ways, or puts it on four legs without ever holding it flat in the
air. There is one command for each:

```
make wrist       # turn it flat in the air: wrist 1 turns 90 degrees, every other joint stays still
make whole-arm   # turn it flat in the air: the whole arm moves, so the gripped edge stays where it is
make tilt        # rest it on the two far legs, then tilt it down onto all four: a table
```

Everything runs in simulation. The first run downloads the environment, a few
gigabytes. On macOS the first start after that is slow too — minutes before
the arm moves — because every newly installed library is checked the first
time it loads.

This folder is a project of its own. It began as a copy of
`../v2-assemble-table`, but it shares no code, configuration or environment
with it or with any other folder.

## The room

- a UR5e arm, bolted to the floor, with a camera on its wrist and a
  two-finger gripper — the same as v2's;
- a table top, a thin board 24–30 cm by 16–20 cm and 1.6–2.0 cm thick,
  **standing upright on one long edge**, 50–55 cm to the arm's left, a face
  towards the arm, give or take 8°;
- two grey holders, one at each end of the top, 5–6 cm tall. Each is a U seen
  from above: a jaw either side of the board and a wall across its end, with
  1.5 mm of play. The top can neither tip nor slide. The only way out is
  straight up;
- four legs, 15–17 cm tall and 2.5–3.5 cm square, **already standing where
  the table goes**, to the arm's right, the far two 76–80 cm out. They stand
  for a table the size of the top: the far two where its far edge will rest
  on their middles, the near two just in from its near edge. Standing them
  there is v2's job. The two air turns leave them alone.

**The arm is told nothing about the room.** It knows where it is bolted down
and how its own gripper and camera are built. The floor height, the top's
size and pose, and where the legs stand and how tall they are are drawn at
random for each run, and it has to measure them. A
test fails if any robot code so much as imports the simulator's numbers.

## What the arm does

1. **Looks round the room** with its camera, and finds the floor and the top.
2. **Measures the top close up**: length, width, thickness, and where its
   upper edge is. It only goes on if the top stands within 5° of upright.
3. **Plans the whole move before touching the top**: the grip, the lift, the
   carry and the turn, with every pose checked. If no grip can do all of
   it, it stops there and says why.
4. **Grips the middle of the upper edge from straight above**, a finger
   either side, 5 cm down over the edge.
5. **Lifts it straight up** until its lower edge is 4 cm above where its
   upper edge was. The camera never sees the holders: grey this close to a
   part is taken for the part's own shadowed sides. So the arm cannot size
   the lift to them, but whatever holds a board upright holds it below its
   upper edge.
6. **Carries it round, hanging**, to the turning spot: the middle of the
   gripped edge goes 50 cm straight in front of the arm, 40 cm up. On the way
   it turns the top about the vertical so that its gripped edge runs exactly
   along wrist 1's axis.
7. **Turns it flat**, a quarter turn, swinging away from the arm — by the
   wrist or by the whole arm.
8. **Holds it flat for 5 seconds**, then reports what every joint did and
   whether the fingers still feel the top.

### The two turns

**By the wrist (`make wrist`).** Wrist 1 turns 90° and nothing else moves.
MoveIt is not asked for this move, because given a goal one joint away its
planner may still wander the others. The trajectory is built joint angle by
joint angle, checked for collisions every 2°, and sent straight to the
controller. It speeds up and slows down smoothly, within the same limits as
every other move with a part in hand. The board turns about wrist 1's axis,
not about its own edge, so it ends up about 30 cm higher and further out.

**By the whole arm (`make whole-arm`).** The board turns about its own
gripped edge, like a drawbridge, in 5° steps. MoveIt's straight-line path
service works out all six joints for every step, so any joint is free to
move. With the edge along wrist 1's axis, only the three joints that bend the
arm in its own plane need to: the shoulder, the elbow and wrist 1.

**Why the edge is lined up with wrist 1's axis.** Turning wrist 1 alone
leaves the board tilted by exactly the angle between its edge and that axis.
At the turning spot, wrist 1's axis is about 15° away from "square across
the line from the base", because the UR5e's shoulder is offset to one side. So
the arm works the axis out from its own model, not from where it is pointing.

### Onto the legs (`make tilt`)

After step 4, instead of carrying the top to the turning spot:

1. **It measures the legs close up**, from above and from its own side, before
   it touches the top — hanging over them, the top would hide them. It works
   out which two are the far ones, and the line across their middles and tops
   that the top's lower edge will rest on. If the near legs would not end up
   under the top, it stops there and says so.
2. **It plans every pose** of what follows, as for the air turns, and checks
   the arm can go through them one after another.
3. **It leans the top 20° towards itself, in the air**, 45 cm out, turning it
   about its gripped edge — or 30° if it cannot reach the far legs leaning
   only 20°.
4. **It carries it out, leaning, over the far legs**, its lower edge 5 cm
   above them.
5. **It lets it down onto them**, feeling for them: half a millimetre at a
   time, reading its own joints' efforts, until the shoulder, elbow or wrist 1
   suddenly has less to hold up. Then it goes back up the one step.
6. **It tilts the top down towards itself about the edge resting on the
   legs**, until it is 3 mm above the near legs. That edge stays where it is
   the whole way, so nothing slides on the leg tops.
7. **It lets go**, and the top falls the last 3 mm onto the near legs. Then
   it pulls the fingers back out from under it and lifts clear.
8. **It looks at the table and checks it**: its height against what it
   should be, and how far from level the top is.

Why it leans the top first, rather than lowering it upright as
[`docs/approaches/tilt-onto-legs.md`](docs/approaches/tilt-onto-legs.md) planned: upright, the top hangs its
whole width plus 12 cm above the far legs, and they have to stand far enough
out — about 78 cm — that the arm can let go of the flat top without folding
up, where it cannot reach that high. The end of that file lists every way
the build differs from the plan.

## What came out

Seed 1: a 24.4 x 16.5 x 1.9 cm top of 0.31 kg. Both turns run at a tenth of
the arm's speed. "Moved" is how far each joint travelled during the turn;
"peak" is the most effort it took, as the simulator reports it.

| Joint | Wrist: moved | Wrist: peak N·m | Whole arm: moved | Whole arm: peak N·m |
| --- | --- | --- | --- | --- |
| base | 0.0° | 0.35 | 0.0° | 0.30 |
| shoulder | 0.0° | 26.8 | 17.0° | 25.3 |
| elbow | 0.0° | 28.7 | 51.3° | 27.2 |
| wrist 1 | **90.0°** | **4.54** | **141.8°** | **4.19** |
| wrist 2 | 0.0° | 0.04 | 0.0° | 0.04 |
| wrist 3 | 0.0° | 0.04 | 0.0° | 0.04 |
| how long | 7.7 s | | 8.6 s | |

Both left the top flat and still held. Asked directly afterwards, Gazebo had
it level to within 0.005° both times: 72 cm up after the wrist turn, and 40 cm
up, its edge where it started, after the whole-arm turn. Seed 7, a top 19.4 cm
wide, came out the same.

It agrees with the calculation in [`docs/approaches/one-joint-or-many.md`](docs/approaches/one-joint-or-many.md):

- the whole-arm turn makes wrist 1 turn 142°, not 90, because the shoulder and
  elbow tilt the forearm as they carry the wrist round;
- the base and wrists 2 and 3 do nothing either way;
- wrist 1's effort is about the same either way, around 4–5 N·m, far below
  its 28 N·m limit, because nearly all of it is holding the weight up, and
  that depends on where things are, not on which joints put them there.

### A heavier top

`DENSITY` sets the top's density, in kg/m³, without changing its size. The
robot is not told. For the seed 1 top:

| `DENSITY` | Mass | What happened (Gazebo's view) |
| --- | --- | --- |
| 400 (usual) | 0.31 kg | Flat and held, both turns. |
| 2000 | 1.53 kg | Flat and held by the wrist turn, drooping 1° in the fingers. |
| 3000 | 2.29 kg | The wrist turn: it twisted in the fingers near the end, and hung 45° off flat. |
| 4000 | 3.06 kg | The wrist turn: fell out 87° into the turn. |
| 5000 | 3.82 kg | Fell out about 47° into the turn, both ways. |

Every one of these was picked up, lifted out and carried hanging without
trouble. It is the turn that the grip cannot take: hanging, the weight pulls
straight along the fingers; flat, it tries to twist the board out of them. It
fails at the same point whichever way the top is turned, because the pull on
the grip depends on the board's angle, not on which joints turned it.

The simulated grip holds more than the rough 0.8 kg estimate in
`one-joint-or-many.md`, but the limit is still the grip, never a joint.

The robot's own report can only go so far. Its fingertip sensors are on the
tip pads only: they say when the top has gone from those pads, and the report
gives how far into the turn that happened. They cannot tell a top that has
twisted down in the fingers from one that has fallen, and a top drooping a
degree or two still counts as held. To see where the top really is, ask the
simulator:

```
pixi run gz model -m table_top -p
```

### Onto the legs

`make tilt` made a table every time, in four different rooms and with tops
up to 3.8 kg — the same heavy tops that could not be turned flat in the air:

| Top | Table height (expected) | Top off level | Worst leg afterwards |
| --- | --- | --- | --- |
| 0.31–0.39 kg, seeds 1, 2, 3, 7 | within 1 mm | 0.0° | moved 1.0 mm or less |
| 2.29 kg (`DENSITY=3000`) | 18.6 cm (18.6) | 0.0° | moved 2.2 mm |
| 3.06 kg (`DENSITY=4000`) | 18.6 cm (18.6) | 0.0° | moved 1.9 mm |
| 3.82 kg (`DENSITY=5000`) | 18.6 cm (18.6) | 0.1° | moved 2.7 mm |

Every leg was still standing. The first version leaned the top 30° in the
air rather than 20°, and with it the 3.06 kg top sagged in the fingers,
twisted out during the tilt and knocked all four legs over. All the numbers,
and what they cannot tell, are in [`docs/turn-results.md`](docs/turn-results.md),
section 5.

## Commands

```
make             # list everything you can run
make wrist       # build if needed, start the cell, turn the top by wrist 1 alone
make whole-arm   # the same, turning it with the whole arm about its edge
make tilt        # the same, putting it on the legs: rest on two, tilt down onto four
make cell        # start the cell but leave the arm alone
make test        # run the tests that need no simulator
make lint        # check code style
make doctor      # print versions of everything that matters
```

Settings, for any of the running commands:

```
make wrist SEED=7            # a different room
make whole-arm DENSITY=3000  # a heavier top
make tilt DENSITY=3000       # a heavier top, onto the legs
make tilt LEG_DENSITY=200    # lighter legs (500, pine, if not given)
make tilt SIZE=2             # top and legs twice as big, and 8 times as heavy
make wrist GUI=false         # no Gazebo window
make wrist RVIZ=true         # also open RViz to see what MoveIt plans against
```

After the report the cell stays up, with the top held flat or lying on the
legs, until you press Ctrl-C. If another project's cell is running at the same time, give this one
its own ROS domain and Gazebo partition, or the two talk over each other:

```
ROS_DOMAIN_ID=42 GZ_PARTITION=v3 make wrist
GZ_PARTITION=v3 pixi run gz model -m table_top -p
```

## Where the code is

```
src/turn_top_flat/
├── launch/                  starting the cell and the task
├── test/                    tests that need no simulator
└── turn_top_flat/
    ├── task.py              the order of everything: both turns, and the tilt onto the legs
    ├── assembly/grasps.py   where the tool goes: the grip, the carry, the turns, the tilt (no ROS)
    ├── assembly/table.py    which legs are which, and the line the top tilts down about (no ROS)
    ├── arm/motion.py        moving the arm, turning one joint alone, recording the joints
    ├── perception/          camera pixels to floor, top and obstacles (no ROS)
    └── world/               the simulator's side: the holders, this run's top, and the legs
src/turn_top_flat_moveit_config/   what MoveIt needs to know about the robot
```

## The plan, in two parts

**Part 1 — the 90° turn: one joint, or many? Built: `make wrist` and
`make whole-arm`.**

The top has to turn 90 degrees, from hanging to flat. The arm can do that by
turning a single joint, wrist 1, and holding all the others still. Or it can
move several joints together, so that one chosen point of the board — here,
the gripped edge — stays still while the board turns about it.
[`docs/approaches/one-joint-or-many.md`](docs/approaches/one-joint-or-many.md) works out what that choice
does to the arm: the torque on every joint, how fast each one has to turn,
and what a joint's real limits mean for which way to go.

**Part 2 — onto the legs, two first. Built: `make tilt`.**

Rather than turn the top flat in the air and set it down on all four legs at
once, the arm rests the top's lower edge on the two far legs first. Then it
turns the top down about that edge, moving the arm as it goes, until the top
touches and settles on all four legs. It is how a person puts a heavy top on
a table. → [`docs/approaches/tilt-onto-legs.md`](docs/approaches/tilt-onto-legs.md)

Both parts sit inside the whole job — look round, measure, stand the legs,
pick the top up, put it down, check the table — which
[`docs/approaches/pick-up-and-place.md`](docs/approaches/pick-up-and-place.md) plans from start to finish,
along with the other ways the top could be turned.

## What each file answers

| File | Question |
| --- | --- |
| [`docs/turn-by-wrist/`](docs/turn-by-wrist/README.md) | **As built.** How does `make wrist` turn the top, step by step, one file per step, written for a beginner? Where does every number come from, which are fixed and which measured? What torque does each joint feel, and could MoveIt have moved just one joint? |
| [`docs/turn-by-whole-arm/`](docs/turn-by-whole-arm/README.md) | **As built.** The same for `make whole-arm`: the 18 poses about the edge, what MoveIt is asked for, and working the joint angles out by hand. Why does wrist 1 turn 142°? |
| [`docs/tilt-onto-legs/`](docs/tilt-onto-legs/README.md) | **As built.** How does `make tilt` put the top on the legs, step by step, for a beginner? Measuring the legs, planning backwards from the table, feeling for the legs with the joints, tilting about the resting edge, and checking the table. |
| [`docs/wrist-or-whole-arm.md`](docs/wrist-or-whole-arm.md) | **As built.** What is really different between the two turns: torque, force on the grip, space, time, and how certain the path is. |
| [`docs/turn-results.md`](docs/turn-results.md) | What each run in Gazebo reported, light top and heavy, in the air and onto the legs. |
| [`docs/approaches/one-joint-or-many.md`](docs/approaches/one-joint-or-many.md) | **Part 1.** To turn the top 90°, is it harder on the arm to turn one joint or several? Worked out joint by joint on the robot. What real limits does a joint have, and which way do they push the design? How heavy a top can the turn take, and how is weight set in Gazebo? |
| [`docs/approaches/tilt-onto-legs.md`](docs/approaches/tilt-onto-legs.md) | **Part 2, built as `make tilt`.** Resting the top on two legs first, then tilting it down onto four: how it works, and what can go wrong — mostly, legs being knocked over. Its last section says where the build differs from the plan. |
| [`docs/approaches/pick-up-and-place.md`](docs/approaches/pick-up-and-place.md) | The whole job, from the holders to the finished table. The ways the top could be turned, one of them in full detail, with pseudo code, the libraries and the gripper. |

## The short answers

**Part 1.** Turning with one joint or with several makes almost no difference
to the torque on any joint. Nearly all of a joint's torque is what it takes
just to hold things up, and that depends on where things are, not on which
joints put them there. Turning one joint is also the quicker of the two,
because the other way makes the busiest joint turn further. What does make a
difference is the arm's *posture*: starting the turn with the wrist flipped
takes 28% off the joint that works hardest. The runs above bear out the first
two.

**Why part 2 exists.** For a turn in the air, it is the grip that gives out
first, not a joint: held flat by one edge, a heavy top twists out of the
fingers. Resting the top on the legs before it goes flat means it is never
held flat in the air at all, so much heavier tops become possible — at the
price of having to turn it without knocking a leg over. The runs bear this
out: tops that fell out of the fingers turning flat in the air, up to 3.8 kg,
all made a table this way.

## The pictures

The pictures are in [`docs/figures/`](docs/figures). Each script there draws the
pictures for one file:

| Script | Draws the pictures for |
| --- | --- |
| `docs/figures/pick_up_and_place.py` | `docs/approaches/pick-up-and-place.md` (and holds the drawing helpers the other two use) |
| `docs/figures/one_joint_or_many.py` | `docs/approaches/one-joint-or-many.md` |
| `docs/figures/tilt_onto_legs.py` | `docs/approaches/tilt-onto-legs.md` |
| `docs/figures/joint_torques.py` | the torque charts in `docs/approaches/one-joint-or-many.md`, section 2 |
| `docs/figures/two_turns.py` | `docs/wrist-or-whole-arm.md`, and the arm drawn to scale in `docs/turn-by-wrist/` and `docs/turn-by-whole-arm/` |
| `docs/turn-by-wrist/figures/draw_steps.py` | `docs/turn-by-wrist/` |
| `docs/turn-by-whole-arm/figures/draw_whole_arm.py` | `docs/turn-by-whole-arm/` |
| `docs/tilt-onto-legs/figures/draw_tilt.py` | `docs/tilt-onto-legs/` |

To redraw them, use this project's own environment, which has matplotlib and
numpy. Run `make setup` first if it is not installed yet:

```
cd v3-turn-top-flat/docs/figures
../../.pixi/envs/default/bin/python pick_up_and_place.py
../../.pixi/envs/default/bin/python one_joint_or_many.py
../../.pixi/envs/default/bin/python tilt_onto_legs.py
```

They are sketches to explain the idea, not drawings to scale. The charts use
the robot's real numbers.

`joint_torques.py` is different: it is a calculation, not a sketch. It loads
the robot from `docs/figures/ur5e_v2_gripper.urdf` and needs PyBullet, which the
environment also has. It checks itself before printing anything, and takes
about a minute and a half:

```
cd v3-turn-top-flat/docs/figures
../../.pixi/envs/default/bin/python joint_torques.py
```

`two_turns.py` is a calculation too, on the same robot model: the two turns
as v3 really runs them, with seed 1's top at the turning spot. It checks
itself before drawing anything, and takes a few seconds:

```
cd v3-turn-top-flat/docs/figures
../../.pixi/envs/default/bin/python two_turns.py
```
