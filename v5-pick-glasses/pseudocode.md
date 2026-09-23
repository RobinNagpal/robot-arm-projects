# Pseudo code

A walk through the project at the level of files and functions. It says what
each thing is for and who calls it, and stops short of what happens inside a
function.

This is the map. [`problem-statement.md`](problem-statement.md) says what the
journey is for, [`docs/`](docs/) is the walk itself, and
[`implementation-notes.md`](implementation-notes.md) has the reasoning behind
the choices.

## What is in the cell, and where each thing is described

The project involves a table, an arm, a rack and a few glasses. Each of those
has one folder, and that folder holds everything about it: the model the
simulator loads, the settings it needs, and the code that works with it.

**The table** is in `work_cell/table/`.

- `table.sdf` is the table itself, grey and plain on purpose.
- `layout.py` is the numbers: the table top is at 75 cm and the arm stands on
  it at one edge. Every height anywhere else in the project is a distance from
  here, which is why these two numbers have one home.

**The arm** is in `work_cell/arm/`.

- `arm.urdf.xacro` is the whole robot. It pulls the UR5e in from Universal
  Robots' own package, bolts the gripper and the camera on, and lists which
  joints and sensors `ros2_control` may touch.
- `gripper.urdf.xacro` is the two-finger gripper: the silicone pads, the
  contact sensors on them, and the force sensor at the wrist.
- `controllers.yaml` says which controllers run the joints. Two of them want
  the fingers, and only one runs at a time.
- `dimensions.py` is the numbers the model does not carry: how far the
  fingertips reach past the flange, where the camera sits, how far to stand off
  a glass to measure it, and how far to lift it before weighing it.
- `motion.py` is the `Arm` class, which is everything the arm can be asked to
  do.
  - `move_to_pose()` plans a free move and `move_linear()` moves in a straight
    line.
  - `set_gripper()` opens and closes the fingers to a width;
    `set_gripper_force()` swaps to the force controller and squeezes;
    `gripper_gap` says how far apart the fingers actually are, which is how
    slip is noticed.
  - `wrist_force_z` is the pull along the gripper's own axis, and
    `load_transferred()` asks whether something else has taken the weight.
  - `rotate_tool()` turns the tool about one of its own axes, in place, about a
    point you name. `tilt()` and `turn_over()` are that one function with the
    two angles the task uses.
  - `can_rotate_tool()` asks whether a turn *could* be made from here, without
    making it. The task asks before the fingers close.
  - `descend_until_contact()` feels its way down, and `in_contact` is the pads'
    contact sensors.

**The arm's camera** is in `work_cell/arm/camera/`, because it is bolted to the
arm and moves with it.

- `wrist_camera.urdf.xacro` is the RGB-D sensor.
- `wrist_camera.py` is the `WristCamera` class. `capture()` returns one frame
  together with where the camera was when it took it, which is the only way a
  picture from a moving camera means anything. `View.to_world()` follows the
  ray through a pixel until it meets a horizontal plane you name — that is how
  a glass gets a position without a depth reading. `capture_marker()` reads the
  marker on the rack base, using the dictionary and id that `rack/layout.py`
  defines, so it hunts for the square the rack actually carries.
  The depth it hands over is the depth the camera reported, unaltered: the
  glasses here are opaque, so there is nothing to correct for.

**The glasses** are in `work_cell/glasses/`. Nothing in this folder imports
ROS.

- `shapes.py` invents outlines. `straight()`, `tapered()`, `stemmed()` and
  `short_stemmed()` each draw one kind at proportions you give. `build()` draws
  one at random proportions, and `family()` draws forty spread across the
  plausible range, which is what the tests use.
- `spawn.py` puts them on the table. `random_glasses()` picks the kinds,
  proportions and positions for a run; `hollow()` finds the inside, from the
  solid base up to the open rim; `revolve()` and `write_mesh()` spin the cut
  face into a closed solid with a real wall thickness; `glass_sdf()` writes
  the model.
- `detect.py` finds them and names them. `standing_on_the_table()` picks out
  whatever is standing higher than the table top,
  `find_glasses()` groups it into one detection per glass, and `classify()`
  says what kind a *measured profile* describes.
- `perception.py` measures one. `row_widths()` reads the silhouette edge to
  edge, `smooth()` takes the wobble out, `raggedness()` decides whether the
  mask was worth trusting, and `profile_from_mask()` puts those together and
  converts pixels to millimetres. `handle_direction()` compares two views to
  find a handle.
- `profile.py` is the `Profile` type and the questions a rule may ask it:
  `widest_at()`, `waist_at()`, `slope()`, `vertical_bands()`,
  `flattest_band()`.
- `spec.py` is the library of kinds — the rule each one uses, where to look,
  and what the gripper may do. It holds no glass measurement.
- `rules.py` applies a kind's rule. `find_grip()` returns where to hold the
  glass and how far to open the fingers, or raises `NoGrip` with a reason.
- `force.py` is the squeeze. `estimate_mass()` guesses from the outline,
  `starting_force()` turns that into the first squeeze,
  `force_for_measured_mass()` corrects it once the glass has been weighed and
  refuses one that is too heavy for its walls, `mass_from_wrist()` reads the
  sensor, and `is_slipping()` compares finger gaps.

**The rack** is in `work_cell/rack/`.

- `rack.sdf` is the base and the marker on it. The marker visual is textured
  with a picture rather than being a plain square; a blank square is invisible
  to the detector.
- `build.py` writes the rack into the world and picks where it stands this run.
  `write_marker()` draws the marker image beside the glass meshes, from the
  same dictionary and id the camera looks for, so the two cannot drift apart.
- `layout.py` is the geometry, and the marker's identity and size, because the
  rack is what carries it. `slots_from_marker()` places all six slots from
  one sighting of the marker. `tilt_budget_deg()` says how far a glass of a
  given width and height may lean going in, and `needs_empty_neighbour()` turns
  that into a yes or no. `usable_slots()`, `slots_consumed()` and
  `fill_order()` are the bookkeeping that follows.

**The room** is in `work_cell/world/`.

- `cell.sdf` is the room and the lighting, with marker lines where the table,
  the rack and the glasses go.
- `build.py` fills those lines in and writes the meshes beside the world file.
- `gz_bridge.yaml` lists the topics that cross from Gazebo into ROS.

## What happens when you type `make run`

`run.launch.py` starts three things: the cell, `move_group`, and the task.

`cell.launch.py` does the work before anything moves.

1. `random_glasses(count, seed)` invents this run's glasses.
2. `build_world()` writes each one as a mesh, splices the table, the rack and
   the glasses into `cell.sdf`, and writes the result to a temporary file.
3. Gazebo starts on that file, `robot_state_publisher` publishes the robot, and
   the bridge connects the topics.
4. The controllers are spawned one after another, the force controller last and
   inactive.

Then `main.py` builds an `Arm`, a `WristCamera`, a `PlanningSceneClient` and a
`PickGlassesTask`, spins ROS on one thread and runs the workflow on the other.

## The workflow

`PickGlassesTask.run()` is the whole of it.

```
wait for the cell, the arm and the camera
tell MoveIt about the table

slots = find the rack               # one sighting of the marker places all six
tell MoveIt about the rack

while there are free slots:
    found = survey the table        # one picture from above
    if nothing left: stop
    target = the nearest glass not already given up on
    tell MoveIt about every glass except this one
    try:
        result = do one glass
    except (unknown shape, not measurable, no grip,
            too heavy, the arm could not):
        write down which glass and why, and do not try it again
    else:
        mark the slots it used as taken
park the arm
report what was racked and what was left standing
```

And one glass, `_do_one()`:

```
profile = look at it from the side and measure it
kind    = classify(profile)                     # from the shape just measured
if no kind fits: leave it standing

if this kind might have a handle:
    take a second view a quarter turn round and find the handle

grip = find_grip(profile, kind, gripper_max_opening)
needs_gap = needs_empty_neighbour(profile.max_width, profile.total_height)
slot = the furthest free slot this glass can use

mass = pick it up and weigh it
turn it over and stand it in the slot
```

`_pick_up()` is where the care is:

```
open the fingers wider than the grip needs
hover above the glass, trying each of the two ways round a parallel
    gripper can hold it, and keep the first one from which the arm
    can still turn the glass over
come straight down to the grip height

squeeze gently until the pads touch
if the width at contact disagrees with the camera by more than 4 mm:
    give up on this glass

squeeze to the estimate from the profile
lift 10 mm and read the wrist sensor
if it is heavier than the estimate:
    set it down, squeeze harder, pick it up again
if it is heavier than its walls can take:
    refuse it

lift clear, and tell MoveIt the arm is now holding it
```

`_invert_and_place()`:

```
lean it over 20 degrees, about the grip point
if the fingers have crept closed: it is slipping, give up

turn it the rest of the way, about the grip point
move above the slot, high enough that the rim clears the rack
come down until something touches
if the rack has not taken the weight: the glass is caught, give up

open the fingers, tell MoveIt it has let go, and lift away
```

## Why the order is what it is

Three orderings in there are not arbitrary, and changing them breaks something
that will not show up immediately.

**Measure, then classify.** Classifying from the overhead view would be
quicker, and it is what the first draft did. It cannot work: a stem is
invisible from directly above, and a tall glass and a short one have the same
silhouette from there. Classifying from the side-on profile means a glass is
never handed a rule its shape cannot support.

**Choose the way round before closing the fingers.** The last wrist joint stops
short of a full turn. Whether the arm can invert a glass therefore depends on
which way round it took hold of it, and a parallel gripper has two ways round
that are otherwise identical. Testing the turn before the grasp costs one
planning attempt; discovering it afterwards means putting the glass back down.

**Weigh before turning over.** The ten-millimetre lift is the last moment a
mistake is free: the glass is off the table and nothing has been inverted. Once
it is upside down, a squeeze that was too light has nowhere to fail gently.
