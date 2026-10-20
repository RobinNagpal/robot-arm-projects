# How to build a simulation world for a lab client

This is the workflow we follow when a lab client brings us a problem. It covers only the simulation setup, not the whole robot solution.

## The main idea

A simulation is only useful if every part of it has a real twin: the arm, each sensor, each camera, each object. So at every step we write down two things: what we use in simulation, and what real hardware it stands for. When we move to hardware, we swap one for the other and the rest of the code stays the same.

## The steps in order

| Step | What we do | What we end up with |
| --- | --- | --- |
| 1 | Visit the lab and collect facts | Photos, measurements, object list, the lab's step-by-step procedure |
| 2 | Choose the simulator | Gazebo, Isaac Sim or MuJoCo, depending on the job |
| 3 | Choose the arm and gripper, get their files | Robot description files that work in simulation and on hardware |
| 4 | Choose the sensors | A table: simulated sensor → real sensor |
| 5 | Choose the cameras | A table: simulated camera → real camera, same settings |
| 6 | Build the bench and room | The layout at real size |
| 7 | Build the objects | One 3D model per object, at real size |
| 8 | Set the physics values | Weight, friction, bounciness and joint resistance that match the real objects |
| 9 | Add moving parts and instrument behaviour | Lids open, the balance reads a weight, the centrifuge says "done" |
| 10 | Check the simulation against the real lab | Fix what doesn't match |
| 11 | Add random changes | Lighting, positions and colours change every run |

---

## Step 1: Visit the lab and collect facts

Before we build anything, we get these from the client:

- **The procedure.** Their written step-by-step instructions for the job.
- **An object list:** every item the arm touches, with brand and part number (for example "Corning Pyrex 5640, 100 mL").
- **Photos** of the bench from several angles, plus each object on its own.
- **Measurements:** bench height and size, distances between instruments, and each object's size (with a tape measure or calipers).
- **Weights:** weigh each object, empty and full.
- **Instrument details:** the model of the balance, centrifuge, sonicator and so on, and how each one talks to a computer (a serial cable, a network, or only a button).
- **Lighting:** windows, ceiling lights, reflections on the bench.

The part number matters most. With it we can find the exact size from the maker's datasheet, so we don't have to guess.

## Step 2: Choose the simulator

| Simulator | Use it for | Weak at |
| --- | --- | --- |
| **Gazebo** | Testing the whole system with ROS and MoveIt; the same code later runs on the real arm | Glass looks unrealistic; no liquids |
| **Isaac Sim** | Realistic pictures of glass, training data for seeing models, simple liquids | Needs an NVIDIA GPU; harder to learn |
| **MuJoCo** | Training learned movement models fast | Pictures are less realistic; weaker ROS link |

**Suggestion:** build the world in Gazebo first, because it is closest to the real system. When we need realistic pictures of glassware to train a seeing model, rebuild the same scene in Isaac Sim, using the same object list and the same sizes.

## Step 3: Choose the arm and gripper, and get their files

1. **Choose the arm** by reach and payload. For example, a bench with several instruments around the arm often needs 500 mm or more of reach and about 1 kg of payload.
2. **Get the robot files from the maker.** Every big arm maker publishes a ROS 2 description package. For example, Universal Robots has `Universal_Robots_ROS2_Description` and Franka has `franka_description`. These include:
   - **URDF / xacro:** the arm's links, joints, joint limits and 3D shapes.
   - **Meshes:** what each part looks like and its collision shape.
3. **Get the gripper files** the same way (for example `robotiq_description`) and attach the gripper to the arm's flange in the xacro.
4. **Add `ros2_control`.** This is the key part for moving to hardware later:
   - In simulation, the arm runs through the `gz_ros2_control` plugin.
   - On real hardware, we change one setting to use the maker's driver (for example `ur_robot_driver`).
   - MoveIt and all our code stay the same.
5. **Make a MoveIt configuration** for the arm and gripper.

| | Simulation | Hardware |
| --- | --- | --- |
| Robot description | Maker's URDF/xacro | **The same file** |
| Joint control | `gz_ros2_control` plugin | Maker's ROS 2 driver |
| Motion planning | MoveIt | **The same MoveIt** |

## Step 4: Choose the sensors (simulation → hardware)

| What we measure | Simulation (Gazebo) | Real hardware examples | What to watch when moving to hardware |
| --- | --- | --- | --- |
| Joint angles, joint torques | `joint_states` from ros2_control | Built into the arm | Same messages, so nothing changes |
| Force at the wrist | `force_torque` sensor | UR e-series built-in sensor, Robotiq FT 300-S, ATI Axia80 | Real readings are noisy and drift, so add noise in simulation |
| Gripper opening and force | Gripper controller | Robotiq 2F-85 status | The real force is not exactly the force you command |
| Touch at the fingers | `contact` sensor (only touching or not) | DIGIT, GelSight | Gazebo's touch is very rough; real touch sensors give images |
| Weight on the balance | `force_torque` under the balance pan, or a small plugin | Mettler Toledo or Sartorius balance over a serial cable | The real balance takes 1–3 s to settle; copy that delay |
| Barcode on a vial | Camera plus decoding software | Keyence, Cognex or Zebra reader, or just a camera | Labels can be curved, dirty or shiny |
| Instrument status ("spin done") | A fake ROS node that answers like the instrument | The instrument's own interface (SiLA 2, OPC UA, serial) | The fake node must use **the same messages** as the real one |
| Safety (a person nearby) | `gpu_lidar` | SICK safety laser scanner, light curtain | On hardware this is wired as safety equipment, not just software |

There are also **simulation-only sensors** with no real twin: the segmentation camera, the bounding-box camera and the logical camera. They give us perfect labels for free, for training and scoring models. Robot code must never use them, or it will fail on hardware. Add a test that fails if robot code reads simulator-only data.

## Step 5: Choose the cameras (simulation → hardware)

### The camera types

| Type | How it works | Real examples | Good at | Bad at |
| --- | --- | --- | --- | --- |
| **Colour (2D)** | A normal picture | RealSense colour stream, Basler, USB cameras | Finding and naming objects, reading labels | No distance |
| **Stereo depth** | Two cameras plus an infrared dot pattern | Intel RealSense D405 (7–50 cm range), D435 (0.3–3 m) | Cheap, close range, works with ROS | Glass, shiny metal, liquids |
| **Time-of-flight depth** | Measures how long light takes to bounce back | Orbbec Femto Bolt / Femto Mega | Plain surfaces, medium range | Glass and shiny surfaces cause wrong readings |
| **Structured light depth** | Projects patterns, very precise | Zivid 2+, Photoneo | Sub-millimetre accuracy, tight tolerances | Expensive and slower |

### Where cameras go

- **On the wrist** (moves with the arm): good for close, exact work like putting a vial in a slot.
- **Fixed above the bench**: sees the whole bench and finds where things are.
- Both need **hand-eye calibration** on hardware, so the robot knows exactly where the camera is.

### The most important mapping point

In Gazebo, every depth camera is a **perfect** depth camera. It has no noise and no holes, and it sees glass as solid. A real stereo depth camera returns almost nothing where there is glass.

So in simulation we must:

1. **Copy the real camera's settings:** resolution, field of view, minimum and maximum range, and frame rate, all from the datasheet.
2. **Add noise** that grows with distance.
3. **Remove depth where there is glass or liquid**, the way the real camera fails.
4. **Place the camera exactly** where it will be mounted on the real cell.

If we skip this, models trained in simulation will look perfect there and then fail on the real camera.

## Step 6: Build the bench and room

- Build the bench, walls and shelves to **real size** from the visit measurements.
- Use **one fixed frame** for everything, for example +X forward, +Y left, +Z up, with the measured bench-top height as the working level.
- Mark where the arm base goes.
- Check that the arm can reach every spot it needs.

## Step 7: Build the objects

There are six ways to get a 3D model, from most accurate to least.

| # | Method | Where to get it | Examples | Accuracy | Use it for |
| --- | --- | --- | --- | --- | --- |
| 1 | **Simple shapes with real sizes** (boxes, cylinders, spheres) | The maker's datasheet plus our own measurements | A 2 mL HPLC vial as a cylinder about 12 × 32 mm; a 50 mL conical tube as a cylinder about 30 × 115 mm; a 96-well plate as a box with the standard SBS footprint of 127.76 × 85.48 mm; a vial tray as a box with holes at the slot spacing from its datasheet | Exact size, simple look | Anything the arm must hit to the millimetre: vial, tray slot, rack hole |
| 2 | **Maker's CAD files** (STEP) | Ask the client, who often already has them from the vendor; the vendor's download portal or support team; 3D ContentCentral; GrabCAD; McMaster-Carr (CAD for most parts it sells) | Arms and grippers (Universal Robots and Robotiq publish STEP files); mounting parts and brackets (McMaster-Carr, Thorlabs); lab instruments such as a centrifuge, balance or autosampler (public downloads are rarer, so ask the vendor for an outer-shape STEP file) | Very accurate | Instruments and hardware. Convert STEP to a mesh (`.dae`, `.obj` or `.stl`) with FreeCAD or Blender |
| 3 | **Hire a CAD designer to model it** | A freelance CAD designer, or an engineering design service | The client's custom rack or holder with no CAD file; an older instrument the maker no longer supports; any part where exact shape matters and nothing else exists | Very accurate (as good as the measurements and photos we give them) | Important objects with no CAD file. Give the designer photos, measurements and ideally the real object; ask for both a STEP file and a mesh. Takes from hours to days per object, depending on how complex it is |
| 4 | **Ready-made 3D model libraries** | Glassware packs on CGTrader, Fab, Superhive (a few dollars each); Thingiverse and Printables (free); Gazebo Fuel; LabUtopia (over 100 lab instruments, built for robot simulation) | Beakers, Erlenmeyer flasks, volumetric flasks, funnels, Büchner flasks | Looks good, size not always exact | Common glassware. Always check and fix the size |
| 5 | **Scan the real object with a phone** | RealityScan or Polycam: walk around the object taking photos, and it builds a 3D model | A custom holder, a worn rack, an odd-shaped tool | Good for odd shapes | The client's own custom items. **Glass cannot be scanned**, because the camera sees through it. Coat it with temporary scanning spray, or use method 1 or 4 instead |
| 6 | **AI makes a 3D model from one photo** | SAM 3D Objects (Meta), TRELLIS.2 (Microsoft), Hunyuan3D (Tencent) | Background items: a notebook, a pen holder, a bottle of cleaner | Fast, but size is unknown and details may be wrong | Background clutter only: things the arm only needs to see, not touch |

**Decision:**

- **Things the arm touches or places precisely:** real sizes from the datasheet or CAD (methods 1 and 2), or a CAD designer if no file exists (method 3). Never trust an AI model's size.
- **Glassware:** use a library model (method 4), then fix its size to the maker's part number. Lab glass is standard, so a Pyrex 100 mL volumetric flask has published sizes.
- **Instruments:** the maker's CAD (method 2), simplified to the outer shape plus any moving parts. If the maker has no file, a CAD designer (method 3).
- **Client-specific custom items:** a phone scan (method 5) or a CAD designer (method 3).
- **Background clutter for training seeing models:** libraries or AI image-to-3D (methods 4 and 6).
- **Using a real photo:** yes, this works. Methods 5 and 6 both start from real photos. We also always use photos to match colour and texture, and to check that the simulation looks like the real bench.

### Each object needs two shapes

| Shape | Where it comes from | Why it matters |
| --- | --- | --- |
| **Visual shape** (what the camera sees) | Any method above | Seeing models train on it |
| **Collision shape** (what physics uses) | A simpler version of the visual shape, split into convex pieces with a tool like CoACD or V-HACD | Detailed shapes make physics slow and jumpy |

Moving parts (lids, caps, drawers, plungers) are separate pieces joined by hinges or sliders; Step 9 covers them. Weight, friction and the other physics values are set in Step 8.

### Liquids

Gazebo cannot simulate flowing liquid. We have three choices:

1. **Fake it.** The liquid is a fixed shape inside the container, and its weight is added to the container. This is good enough for carrying and placing.
2. **Show the fill level as a picture only**, for training seeing models (for example, to check "filled to the mark").
3. **For pouring, use Isaac Sim particles**, or keep it for later.

## Step 8: Set the physics values

The 3D model gives only the shape. For an object to behave like the real one, it also needs physics values: how heavy it is, how it slides, how it tips, how it bounces, and how its moving parts resist.

### The values that matter in a lab

| Value | Simple meaning | Lab example |
| --- | --- | --- |
| **Weight** | How heavy it is | A flask empty and full; a vial tray with 50 vials in it |
| **Balance point** (centre of mass) | The point it balances on | A tall, empty volumetric flask tips easily; with liquid in the bulb it is steadier |
| **Inertia** | How hard it is to turn or swing | A 1 L solvent bottle swung quickly by the arm |
| **Static friction** | How hard you push before it *starts* to slide | A vial held in the gripper pads; a beaker that must not move when bumped |
| **Sliding friction** | How much it resists *while* sliding | A tube rack pushed along the bench |
| **Twist friction** | How much it resists turning in place | A vial spinning in the gripper while a cap is screwed on |
| **Bounciness** | Does it bounce when set down? | A vial dropped into a tray slot must not bounce out |
| **Softness of contact** | How much it squashes when pressed | Rubber septum caps, silicone gripper pads, soft tubing |
| **Joint resistance and springs** | How hard a part is to move, and whether it springs back | Centrifuge lid hinge, balance draft-shield door, pipette or syringe plunger, screw cap |

### Three ways to get the values

**1. Calculate them (weight, balance point, inertia)**

- **Weight:** weigh the real object, empty and full.
- **Balance point:** if we have CAD, the CAD program gives the centre of mass once the material is set (glass, steel, plastic). Without CAD, hang the object from a string at two different points. The balance point is where the two hanging lines cross.
- **Inertia:** always calculated from the shape and weight, never measured by hand. CAD programs give it, and mesh tools such as `trimesh` calculate it from the 3D model.
- **Liquid inside:** add the liquid's weight, and move the balance point down to where the liquid sits.

**2. Look them up, as a starting point only (friction, bounciness)**

Engineering tables list friction for material pairs such as glass on steel or rubber on glass. Use them only to start. Real friction changes when glass is wet after washing, when there is dust or powder on the bench, or when gripper pads wear.

Friction belongs to a **pair** of surfaces, not to one object. Glass on a silicone pad is very different from glass on a steel bench. Most simulators give each object one friction number and **mix the two numbers** when objects touch, and each simulator mixes them differently:

- Gazebo (ODE engine) uses the **smaller** of the two.
- Isaac Sim **averages** them by default.
- MuJoCo uses the **larger** of the two.

So we choose each object's number so that the important pairs come out right. The most important pair is usually the gripper pad on the object.

Lab bench tops are usually epoxy resin, phenolic resin or stainless steel. Always use the client's actual bench material for these values.

**3. Measure with simple tests (the most reliable way)**

These tests need only a phone, a board covered with the bench material, and a cheap force gauge or luggage scale.

| Test | How to do it | What it gives |
| --- | --- | --- |
| **Tilt test** | Put the object on the board. Tilt it slowly until the object starts to slide, and read the angle with a phone level app. Repeat 5 times and take the middle value. | Static friction = tan(angle). Example: slides at 25° → tan(25°) ≈ 0.47 |
| **Pull test** | Pull the object across the bench at a steady speed with a force gauge. | Sliding friction = pull force ÷ object's weight |
| **Gripper slip test** | Hold the object in the real gripper at a known grip force. Pull it down slowly until it slips. | Pad-to-object friction = slip force ÷ (2 × grip force), for a two-finger gripper |
| **Drop test** | Drop the object from a known height and film it in slow motion. Measure how high it bounces back. | Bounciness = square root of (bounce height ÷ drop height) |
| **Push-to-tip test** | Push the object at a set height and note when it tips. | Checks the balance point |
| **Joint test** | Pull a lid or door with a force gauge, and note the distance from the hinge. Press a plunger on a kitchen scale and read the force at full press. Film a lid closing on its own. | Hinge resistance = force × distance; spring stiffness = force ÷ how far it moved; damping = how fast it closes in the video |
| **Squeeze test** (soft items only) | Press with a known force and measure how much it squashes. | Contact softness |

**Safety:** never drop real glass. Use a plastic copy of the same shape for the drop test, or simply set glass bounciness near zero, which is close to the real value.

### Make the simulation match the tests

1. **Run the same test in the simulator.** Tilt the simulated board, pull the simulated object, drop it.
2. **Adjust the simulated value until the result matches the real one.** If the real beaker slides at 25°, change its friction until the simulated beaker also slides at about 25°. This is called **system identification**: making the simulation match reality.
3. **Record a range, not just one number.** Real friction changes from day to day, so note a range around the measured value (about ±20% for friction). Step 11 uses this range.
4. **Write everything in the object sheet:** each value, its range, and where it came from (calculated, looked up, measured or tuned).

### Example: a 100 mL glass beaker on a steel bench

| Value | Where it comes from |
| --- | --- |
| Weight | Weighed empty, and with 50 mL of water |
| Balance point | From CAD or calculated; it moves lower when water is inside |
| Inertia | Calculated from the mesh and the weight |
| Beaker on the bench | Tilt test on a steel sheet → angle → tan(angle) |
| Beaker in the gripper pads | Gripper slip test with the real pads |
| Bounciness | Set near zero; no drop test needed for glass |
| Range for random changes | Friction ±20%, weight ±5% |

## Step 9: Add moving parts and instrument behaviour

- **Moving parts:** the centrifuge lid gets a hinge, a cap gets a twist joint, a drawer gets a slider.
- **Instrument behaviour:** a small fake program for each instrument that acts like the real one.
  - The fake balance reports the weight on its pan.
  - The fake centrifuge says "running", then "done" after the set time.
- **Each fake instrument must use the same messages as the real one.** Then, on hardware, we swap the fake for the real driver and nothing else changes.
- **Ask the client early:** if an instrument has no computer connection, flag it. Prefer instruments the robot can ask "are you done?".

## Step 10: Check the simulation against the real lab

Step 8 matched each object on its own. This step checks the whole scene together:

| Check | How |
| --- | --- |
| Does it look the same? | Put a simulated camera picture next to a real photo from the same spot |
| Is the size and layout right? | Measure objects and distances in simulation and compare with real measurements |
| Do the sensors read the same? | The simulated force sensor and balance must read the real weights; simulated camera pictures must have the same range and noise |
| Can the arm reach everything? | Run a reach check across the bench |
| Does a full task behave the same? | Run one real task step, such as placing a vial in a slot, in both simulation and reality, and compare what happens |

Fix what doesn't match, then check again.

## Step 11: Add random changes

The real lab is never exactly the same twice. In each simulation run we change:

- object positions and angles (a little);
- lighting (brightness, direction);
- colours and textures of the bench and background;
- camera position (a few millimetres, as with a slightly loose mount);
- object weights and friction, within the ranges recorded in Step 8.

---

## What we hand the client after the simulation stage

1. **An object sheet:** one row per object with part number, size, weight, friction, where the 3D model came from, and its real twin.
2. **A sensor and camera sheet:** each simulated sensor next to the real one, with the same settings.
3. **The world files:** one folder per object (`model.config`, `model.sdf`, meshes) and one world file, in git.
4. **A reality-check report:** the Step 8 test results and the Step 10 comparisons, with numbers.
5. **A list of open questions:** for example, an instrument with no computer connection, or a glass object we could not measure.

## Summary

Get exact sizes from part numbers, datasheets and CAD for everything the arm touches, and hire a CAD designer when no file exists. Use model libraries, phone scans or AI only for things it just has to see. Measure friction and other physics values with simple tests, and tune the simulation until it matches them. Give every simulated sensor and camera the same settings and the same faults as the real one, especially depth cameras on glass. That way the move to hardware is a swap, not a rebuild.

---

## Sources

- [LabUtopia (NeurIPS 2025)](https://arxiv.org/pdf/2505.22634), with the [project page](https://rui-li023.github.io/labutopia-site/)
- [Lab glassware set on CGTrader](https://www.cgtrader.com/3d-models/various/various-models/laboratory-glassware-set-hr)
- [Lab glassware on Fab](https://www.fab.com/listings/51f49e06-291d-468b-bdfc-7ee29f114c63)
- [Lab glassware on Superhive](https://superhivemarket.com/products/laboratory-glassware)
- [Lab equipment pack on CGTrader](https://cgtrader.com/3d-models/science/laboratory/laboratory-equipment-material-de-laboratorio)
- [Kipp & Zonen STEP downloads (an example of a vendor CAD portal)](https://www.kippzonen.com/News/632/STEP-files-available-to-download)
- [SAM 3D Objects](https://sourceforge.net/mirror/sam-3d-objects/)
- [Choosing an image-to-3D model for robots (2026)](https://arxiv.org/pdf/2603.27797)
- [NVIDIA SimReady assets](https://developer.nvidia.com/omniverse/simready-assets) (warehouse and factory sets exist; no lab set found)
