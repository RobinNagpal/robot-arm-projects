# Architecture

Two ROS 2 packages under `src/`.

```
v5-pick-glasses/
├── Makefile                     the only entry point people use
├── pixi.toml                    every dependency, pinned in pixi.lock
└── src/
    ├── work_cell/               the cell and the task that runs in it
    │   ├── launch/              how it all gets started
    │   ├── test/                tests that need no simulator
    │   └── work_cell/
    │       ├── arm/             the arm: model, controllers, motion
    │       │   └── camera/      the camera bolted to its wrist
    │       ├── table/           the table, and the frame everything measures from
    │       ├── glasses/         glasses: inventing, finding, measuring, gripping
    │       ├── rack/            the drying rack, and how much room a glass needs
    │       ├── world/           the room, and the bridge into ROS
    │       ├── task.py          the workflow
    │       ├── scene.py         what MoveIt is told about the room
    │       └── transforms.py    shared maths
    └── work_cell_moveit_config/ what MoveIt needs to know about the robot
```

## Why the folders are shaped like this

One folder per thing in the room. `arm/` holds everything about the arm — the
model the simulator loads, the controller settings, the code that moves it —
and `table/`, `glasses/`, `rack/` and `world/` do the same for theirs.

The alternative, and the more common ROS layout, is one folder per file type:
all the models together, all the YAML together, all the Python together. That
reads well when you already know the project, because you know what kind of
file you are looking for. It reads badly when you do not, because answering
"how is the gripper set up?" means opening three folders and knowing in advance
which three.

Grouping by subject means a question about the arm is answered in one place. It
costs one thing: `.xacro` and `.yaml` files sit next to `.py` files, which is
unusual to look at. `setup.py` installs them to the places ROS expects, so
nothing downstream notices.

## The split that matters most here

Cutting across the folders is a second line, and it is the more important one:
**what knows about ROS, and what does not.**

Everything in `glasses/` is plain Python and numpy. Not one file there imports
ROS, and none of them can be given a camera, a robot or a topic. They take
arrays and dataclasses and return arrays and dataclasses.

That is not tidiness. It is what makes the interesting half of this project
testable. The question "does the stem rule work on a wine glass with a
short bowl and a long foot?" has nothing to do with robots, and answering it
should not require starting a simulator. Because `glasses/` is ROS-free, the
test suite draws forty glasses, measures them, applies the rules and checks the
answers — 141 tests in under a second, on any machine, with no Gazebo.

The ROS-facing parts are thin on purpose:

| Module | What it does | Why it cannot be tested offline |
| --- | --- | --- |
| `arm/motion.py` | plans and executes moves, drives the gripper, reads the sensors | it is MoveIt and the controllers |
| `arm/camera/wrist_camera.py` | hands back a frame and where the camera was | it is subscriptions and TF |
| `scene.py` | tells MoveIt what is in the room | it is a service call |
| `task.py` | the order things happen in | it drives the three above |

Everything those four modules *decide* has been pushed down into `glasses/` or
`rack/`, where it can be tested. `task.py` in particular contains no
arithmetic about glasses at all; it asks other modules and acts on the answers.

## Why two packages

`work_cell_moveit_config` holds only configuration: a semantic description of
the robot (which joints are the arm, which are the gripper, which pairs of
links are allowed to touch) and the planner settings. That is the layout
MoveIt's own tooling expects, and keeping it separate means the robot itself is
described in exactly one place — `work_cell/arm/arm.urdf.xacro` — which both
the simulator and MoveIt read.

## work_cell

### The arm

| File | What it owns |
| --- | --- |
| `arm/arm.urdf.xacro` | The whole robot. Pulls the UR5e in from `ur_description`, adds the gripper and camera, and declares which joints and sensors `ros2_control` may touch. |
| `arm/gripper.urdf.xacro` | The two-finger gripper: the silicone pads, their friction and softness, the contact sensors on them, and the force sensor between the flange and the gripper. |
| `arm/controllers.yaml` | The five `ros2_control` controllers. Two of them drive the same finger joints and only one runs at a time — see below. |
| `arm/dimensions.py` | The measurements the model does not carry: fingertip reach, camera offset, working heights, how far to lift before weighing. |
| `arm/motion.py` | The `Arm` class: planning, straight lines, squeezing to a force, turning in place, feeling for contact. |
| `arm/camera/wrist_camera.urdf.xacro` | The RGB-D sensor, and the two frames a ROS camera needs. |
| `arm/camera/wrist_camera.py` | The `WristCamera` class: a frame plus the pose the camera was at, projection onto the table, and the rack marker. |

### The glasses

This is where the project lives.

| File | What it owns |
| --- | --- |
| `glasses/shapes.py` | How to draw a glass outline of a given kind and proportions, and how to draw a whole family of them. Used by the spawner and by the tests. |
| `glasses/spawn.py` | This run's glasses: their kinds, proportions, positions, and the meshes and SDF the simulator loads. |
| `glasses/detect.py` | Finding glasses from above, and deciding what kind a measured profile describes. |
| `glasses/perception.py` | Turning a side-on mask into a profile in millimetres. |
| `glasses/profile.py` | The `Profile` type, and the features a rule can ask it for: widest point, waist, slope, vertical bands. |
| `glasses/spec.py` | The library of kinds. Rules and limits only — never a size. |
| `glasses/rules.py` | Applying a kind's rule to a profile to get a grip, and rejecting the answer when it is not one the gripper can make. |
| `glasses/force.py` | How hard to squeeze: the estimate before lifting, the correction after weighing, and the caps. |
| `glasses/glass.sdf` | The template one glass model is built from. There are no meshes here; they are made per run. |

### The rack

| File | What it owns |
| --- | --- |
| `rack/layout.py` | Where the six slots are, given where the marker was seen, and the tilt budget that decides whether a glass needs the slot beside it left empty. |
| `rack/build.py` | The rack's SDF, and where it stands this run. |
| `rack/rack.sdf` | The base and the marker. |

### The rest

| File | What it owns |
| --- | --- |
| `table/layout.py` | The one place the table's height and the robot's base are written down. Everything else measures from these. |
| `table/table.sdf` | The table model. |
| `world/cell.sdf` | The room and the lighting, with marker lines for the parts that change. |
| `world/build.py` | Assembling the room, the table, the rack and this run's glasses into one world file, and writing the meshes beside it. |
| `world/gz_bridge.yaml` | Which topics cross from Gazebo into ROS. |
| `task.py` | The workflow, and nothing else. |
| `scene.py` | What MoveIt is told is in the room, including the glass currently in the gripper. |
| `transforms.py` | Poses, quaternions and tool orientations. |

## Two controllers for two fingers

`arm/controllers.yaml` declares both a `gripper_controller` (position) and a
`gripper_force_controller` (effort) on the same two joints. They cannot both
run, because two controllers may not command one joint, so the force one is
loaded inactive at startup and `arm/motion.py` swaps them over.

The swap happens at exactly two moments. `set_gripper_force()` takes the joints
for the force controller when the pads reach the glass, and `set_gripper()`
takes them back for the position controller to let go.

This is worth the complication because the alternative does not work. A
position controller told to close on a glass keeps driving towards a number the
glass is in the way of, and what happens next depends on the joint's effort
limit rather than on anything the task decided. Holding a glass is a statement
about force, so it is made with a force command.
