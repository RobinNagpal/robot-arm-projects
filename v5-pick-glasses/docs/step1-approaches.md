# Step 1 — other ways to find a glass

[`step1-finding-the-glasses.md`](step1-finding-the-glasses.md) explains how the
arm finds glasses today. This document puts that method next to the others, so
they can be compared and one can be chosen. Each one is explained from the
start. Nothing here assumes you know robotics.

The others come in two groups:

- **Approaches 1 to 6 change the sensor**, or where it stands: fixed cameras, a
  lidar, the fingers, a force plate.
- **Approaches 7 to 12 keep the camera** and change how a picture is read: which
  pixels in it are a glass. This is the part that matters most for real,
  see-through glass.

Most of these have a longer treatment in the **object perception** area of
robotics-basics, and each one below links to it. The two documents that cover
the most ground here are
[the sensors](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md), for the first group, and
[methods you write yourself](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md) with
[models that find](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md), for the second.

## What "finding a glass" means

Before the arm can pick up a glass, it needs two answers:

1. **Where is it?** A point on the table, in millimetres from the robot's base.
2. **What shape is it?** Its width at every height, from the table to the rim.
   This is called the **profile**.

Step 1 answers the first question. Step 2 answers the second. Some of the
methods below answer both at once, so this document covers both.

Two words matter when judging a method:

- **Accurate** means the answer is close to the truth. If the glass is at
  400 mm and the arm says 402 mm, that is accurate.
- **Precise** means the answer is the same every time you ask. If the arm says
  430 mm on every run, that is precise but not accurate. It is wrong by the
  same amount each time.

The current method is fairly precise, but not accurate enough. The docs record
the survey as about 30 mm out along one direction, which is enough for the
fingers to arrive beside the glass instead of around it.

## A few words used below

- **Pixel.** One dot in a picture. The camera here takes pictures 320 dots
  wide and 240 tall.
- **Depth camera.** A camera whose pictures hold a distance in each pixel
  instead of a colour: "the thing at this dot is 0.43 m away."
- **Mask.** A picture where every pixel is just yes or no: "is this pixel part
  of a glass?"
- **Fixed camera.** A camera bolted to the room or the table. It never moves,
  so its position is measured once and written down, like the table's height.
  The wrist camera, by contrast, moves with the arm.

## How each method is judged

Every method below is looked at against the same five questions.

1. **How accurate is it?** Is the answer close to where the glass really is?
2. **Does it help short glasses?** Short glasses are where runs fail today.
   The wrist camera and the fingers cannot get low enough to see or touch a
   glass that is only 60 mm tall.
3. **Would it work on real glass?** Here the glasses are opaque. That is an
   assumption, and a real kitchen would take it away first.
4. **What has to be added?** A new sensor, new code, or both.
5. **Does it keep the project's rule?** No glass's size may be written down
   anywhere. The arm may only know the cell, meaning the table, its own body
   and the sensors bolted to them. It must measure every glass itself.

---

## 0. What we do now: the wrist camera looks down from above

Longer treatment: the position comes from
[the plane the object stands on](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#22-the-plane-the-object-stands-on),
the separating of one glass from another is
[connected components](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#13-edges-contours-and-connected-components),
and the reason a single picture cannot do it alone is
[why one picture has no size](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/01_overview.md#5-why-one-picture-has-no-size).

### The idea

The arm lifts its wrist camera 450 mm above the table and points it straight
down. Anything that stands above the table top is a glass. Each glass is placed
by tracing its outline down to the table. A second picture, taken 120 mm to one
side, corrects for the glass's top standing in the air rather than on the
table. [`step1-finding-the-glasses.md`](step1-finding-the-glasses.md) goes
through every part of this, and why one picture is not enough.

### Good

- No new hardware. The camera is already on the wrist.
- No training and no stored glass sizes. It works on any glass it has never
  seen.
- It fails honestly. A pixel with no distance is dropped, not guessed.

### Bad

- **It barely uses the depth.** The depth picture already says how far away
  each glass pixel is. The code only uses that to answer "is this glass, yes or
  no". The position is then worked out by tracing lines down to the table,
  which is a leftover from when the glasses were treated as see-through and had
  no depth reading at all.
- **It is slow.** Several stations, two pictures each, and an arm move between
  every picture.
- **It is still about 30 mm out**, and nobody has yet found why.

Its other weak points, such as two touching glasses reading as one, are listed
under *Where this approach can fail* in the step 1 document.

### Short glasses

It finds them. The problem with short glasses comes later, in step 2, when the
camera has to look from the side and cannot get low enough.

### Real glass

It fails. A real depth camera gets almost no distance back from glass, so no
pixel is marked as standing above the table.

### A change that needs no new hardware

Because the glasses are opaque, every glass pixel has a real distance. Each one
can become a real 3D point in the room, with no tracing down to the table:

1. Turn every glass pixel into a 3D point, using its distance and the camera's
   position.
2. Keep the highest points. They are the rim.
3. Fit a circle through them. A glass is round and upright, so the middle of
   the rim is straight above the middle of the foot. **That is where it
   stands.**
4. How high the rim sits above the table is **the glass's height.**

This would replace the second picture and the 1.5 times correction. It would
not help step 2 see low down, which is a separate problem.

---

## 1. A fixed camera above the table

Longer treatment: [where to put the
camera](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#14-where-to-put-the-camera), which compares a camera
on the wrist against one bolted to the room.

### The idea

Bolt one depth camera high above the table, looking straight down, for
example 1.5 m up. It sees the whole table in one picture, and the arm does not
have to move at all to take it.

### The steps

1. Measure once where the camera is bolted and which way it points. Write that
   down with the table's numbers, because it is part of the cell.
2. Take one depth picture of the whole table.
3. Find the glass pixels, exactly as today: anything above the table top.
4. Turn them into 3D points and fit a circle to each rim, as in the change
   above.
5. Hand the positions to the arm.

### Good

- **One picture, no arm moves.** Finding every glass on the table takes a
  fraction of a second.
- **The camera is always in the same place**, so its errors are the same every
  run and can be measured and corrected once.
- **Less lean error.** A glass's top stands in the air, so tracing it down to
  the table puts the glass too far out. That error shrinks when the camera is
  further away. At 1.5 m, a 150 mm glass is pushed out by 1.11 times, instead
  of 1.5. With the 3D points and circle fit, the lean does not matter at all.
- **The arm is not in the way**, as long as it is parked out of the picture.

### Bad

- **Each pixel covers more table.** A camera further away sees more, but in
  less detail. With today's 320 × 240 camera at 1.5 m, one pixel covers about
  5 mm of table, which is too coarse. It needs a sharper camera, for example
  1280 × 960, to get down to about 1.4 mm per pixel. In Gazebo that is a
  setting. The cost is a slower simulation.
- **It still cannot see a stem.** Side-on measuring is still needed.
- **It adds a fact to the cell.** The problem statement says the arm knows
  itself and nothing else. A fixed camera is part of the cell, like the table,
  so this fits the idea behind the rule. The problem statement would need a
  sentence saying so.

### Short glasses

Finding them: yes, easily. Measuring their shape: no, because a view from
above cannot see the shape.

### Real glass

It fails, for the same reason as today. The depth camera sees through the
glass.

---

## 2. A fixed camera at the side, at table level

Longer treatment: [where to put the
camera](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#14-where-to-put-the-camera) again, and
[how the four sensing principles fail](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#11-how-the-four-sensing-principles-fail)
for what a depth sensor at this angle would and would not return.

### The idea

Bolt a camera at the edge of the table, only a few centimetres above the table
top, looking level across the glasses. It sees each glass from the side, the
way a person crouching at the table would. This is the view step 2 needs, and
the camera can sit lower than the wrist camera can ever get.

### The steps

1. Bolt the camera about 30 mm above the table, at the edge nearest the
   glasses, looking across them. Measure its position once.
2. Take one picture. Every glass appears as an outline standing on the table
   line.
3. Find where each glass is from above, with the current method or with
   approach 1. That gives the distance from the camera to each glass.
4. The distance turns pixels into millimetres. This is the same sum step 2
   uses today: one pixel covers `distance / fx` metres, where `fx` is a number
   that comes with the lens.
5. Read the width of the outline at every height. That is the profile.

A second camera at right angles to the first helps. Glasses standing in a line
hide each other from one side, but not from both.

Two side cameras can also *find* the glasses without any view from above. Each
camera says which direction a glass lies in, and two directions cross at one
point.

### Good

- **It sees the foot of a short glass clearly.** This is the direct answer to
  the short-glass problem in measuring. The camera is already at table level,
  so it never has to be carried down there.
- **No arm moves** to measure. Every glass is measured from the same picture.
- **The distance is known the same way it is today**, from where the glass
  stands. No depth reading of the glass is needed.
- **It is how factories measure real glass.** They put a lit panel behind the
  glasses. Glass bends light at its edges, so each glass shows up as a dark
  outline against the bright panel, even when it is clear. This is one of the
  few methods here that would keep working if the opacity assumption were
  dropped.

### Bad

- **Glasses hide each other.** One glass behind another is one outline. A
  second camera fixes most of this. Glasses set out in a tidy grid fix the
  rest.
- **The arm can get in the picture.** Measuring should happen while the arm is
  parked out of the way.
- **The height of the camera limits the view.** A camera at 30 mm looking level
  sees the side of a glass well. For a very tall glass, the rim is at a steep
  angle, and a wide lens is needed to fit it in.
- **The distance has to be right.** A glass 10 mm further away than believed is
  measured about 3% too small. The finding step has to be good for this one to
  be good.
- **It is new hardware** in the cell, with a position that has to be written
  down and trusted.

### Short glasses

Yes. This is the method that helps them most.

### Real glass

Yes, with a lit panel behind the glasses.

---

## 3. Feeling with the fingers

Longer treatment: [measuring by touch](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#2-measuring-by-touch)
and [measuring by touching it](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#27-measuring-by-touching-it).
Both make the same two points this section runs into — that touch is the most
accurate instrument an arm has, and that it is useless as a survey instrument,
because you have to know roughly where to reach before you can reach.

### The idea

Use the gripper as a measuring tool, like a person feeling the shape of an
object in the dark. The fingers open wide, go round the glass, and close gently
at one height after another. Where they stop at each height is the width of
the glass there.

### The steps

1. The glass must already be roughly found, by one of the other methods. Touch
   measures a glass. It does not find one.
2. Open the fingers wider than the glass.
3. Move the fingers to the top of the glass.
4. Close gently, with about 1 N, until the contact sensors in the pads say they
   have touched.
5. Record the gap between the fingers. That is the width at this height.
6. Open, move down 2 mm, and repeat.
7. At the bottom, the list of widths is the profile.

### Good

- **It measures exactly what the fingers will hold.** No camera, no pixels, no
  conversion. A width measured by touch is the true width.
- **It works on real glass.** Touch does not care whether light goes through.
- **It needs no new hardware.** The contact sensors in the pads and the finger
  gap reading already exist.

### Bad

- **It is slow.** 2 mm steps up a 150 mm glass is 75 closes. At a second or two
  each, that is two or three minutes for one glass. Bigger steps are faster but
  miss detail, such as a thin stem.
- **Every touch is a risk.** If one finger arrives before the other, it pushes
  the glass sideways. A light glass can slide or tip. This project treats a
  knocked glass as the worst outcome.
- **It cannot reach low.** The fingers come in level, and the gripper's body is
  a 90 mm box. Below about 50 mm, the body hits the table. That is the same
  limit that stops short glasses being gripped.

### Short glasses

No. The fingers cannot get low enough, for the same reason they cannot grip
there.

### Real glass

Yes.

### Where it fits best

As a check, not as the main method. Touch the glass at two or three heights
around where the grip will be, and compare with the camera's profile. The arm
already does this once: it compares the width at first contact with the
camera's width, and refuses the glass if they differ by more than 4 mm.

---

## 4. A lidar scanning flat across the table

Longer treatment: [LiDAR, and why it is almost never on the
arm](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#12-lidar-and-why-it-is-almost-never-on-the-arm), which
also makes the point that a time-of-flight depth camera already *is* a lidar —
the formal term is scannerless lidar — so half of this option is in the cell
already.

### The idea

A **lidar** sends out a beam of light that sweeps round in a flat circle, and
times how long each flash takes to come back. That gives a distance in each
direction, like a depth camera squashed into a single line. Put one just above
the table top, and it sees a thin slice through the bottom of every glass.

### The steps

1. Bolt a lidar about 20 mm above the table, at a corner, so its beam sweeps
   flat across the glass area.
2. Each sweep returns a few hundred points. Each point is a spot where the beam
   hit something.
3. Points on a glass form a curve: the near side of a circle.
4. Fit a circle to each curve. The middle of the circle is **where the glass
   stands**, and its size is **the width of the foot**.
5. More lidars at other heights, for example 50 mm and 100 mm, give the width
   at those heights too, which is a rough profile.

### Good

- **Very accurate position.** A lidar measures distance directly, often to a
  millimetre or two, and a circle fit uses many points at once.
- **Fast.** One sweep sees every glass.
- **Gazebo supports it.** It has a `gpu_lidar` sensor that can be added to the
  cell model.

### Bad

- **It only sees the near side of each glass**, and glasses hide each other,
  as with the side camera. A second lidar in another corner helps.
- **Only a few heights.** One lidar gives one slice. A full profile needs a
  camera, or many lidars.
- **New hardware**, like the fixed cameras.

### Short glasses

It finds them well, because it looks at the foot, which every glass has. It
does not measure their full shape.

### Real glass

No. The beam goes through the glass, or bounces off it in the wrong direction.

---

## 5. Infrared or capacitive sensors in the fingertips

Longer treatment: [infrared, in four different
roles](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#13-infrared-in-four-different-roles). The role wanted
here is called **pre-touch**, and it is also listed among
[what touch can actually do](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#21-what-you-can-actually-do-with-it).

### The idea

Put a small sensor in each fingertip that can tell something is close
*before* it touches.

- **Infrared.** It shines invisible light and measures how much bounces back.
- **Capacitive.** It senses a change in the electric field around it when
  something comes near, which is how a phone screen feels a finger.

### The steps

1. The glass is roughly found by another method.
2. The fingers move slowly towards the glass.
3. The sensors report "something is 3 mm away" before any contact happens.
4. The arm stops, and records where the edge of the glass is.
5. Doing this at a few heights, or from a few sides, gives edges, width and the
   centre, all without touching.

### Good

- **No touching**, so no risk of pushing the glass.
- **It checks the last few millimetres**, exactly where the camera is weakest.
  This is where the fingers arrive beside a glass instead of around it today.
- **Capacitive sensing works on real glass.**

### Bad

- **Gazebo has no such sensor.** It would have to be faked, for example with a
  very short-range lidar beam in each fingertip.
- **Slow as a way to measure a whole glass**, for the same reason as touch.
- **Same low limit as touch.** The fingers still cannot reach below about
  50 mm.

### Short glasses

No, for the same reason as touch.

### Real glass

Capacitive: yes. Infrared: poorly, because much of the light goes through.

---

## 6. A force plate under the table

### The idea

Put a weighing sensor, called a **load cell**, under each corner of the table,
or under a plate the glasses stand on. When a glass stands on it, each corner
feels part of its weight. The corner nearest the glass feels the most.
Comparing the four readings tells you where the weight is.

### The steps

1. Weigh the empty table and remember the readings.
2. With glasses on the table, read the four corners again.
3. The difference is the weight of the glasses.
4. How that weight is shared between the corners gives the point where the
   weight is centred.

### Good

- **It finds a single glass's position and weight at once.** Step 5 could know
  the weight before lifting, instead of estimating it.
- **It does not care about looks.** Clear, painted or dark makes no
  difference.
- **It notices changes.** If the reading shifts when nothing was supposed to
  happen, something has moved or fallen over.

### Bad

- **Several glasses give one answer.** With three glasses on the table, it
  reports one centre point for all three, which is not where any of them
  stands.
- **It works by difference only.** Reading it just before and just after a
  pick tells you the weight of the glass taken, and where it was. That is
  useful for checking, not for finding.
- **Real load cells drift**, and the table vibrates when the arm moves.
- **It is new hardware under the furniture.**

### Short glasses

It finds them only one at a time.

### Real glass

Yes.

---

## The second group: which pixels are a glass?

Every method so far changes the sensor. The next six keep the wrist camera and
change one thing: how the arm decides which pixels in a picture are a glass.

Today that decision is one function, `standing_on_the_table()` in
`glasses/detect.py`. It answers "is this pixel higher than the table top?" and
hands back a mask. Everything after it, including placing the glass and
measuring its profile, only ever sees that mask. So any of the methods below
could replace that one function, and nothing downstream would change.

---

## 7. Colour

Longer treatment: [a colour range](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#11-a-colour-range).
It is worth reading for the HSV point alone: do the threshold in hue,
saturation and value rather than in red, green and blue, so that a shadow
changes the brightness and leaves the colour alone.

### The idea

The glasses in this cell are painted, each a different solid colour. Look for
pixels of that colour.

### Good

- It is about three lines of [OpenCV](https://github.com/opencv/opencv), and it
  would work perfectly here.

### Bad

- **It works in this cell and nowhere else.** The paint is there so that a
  person watching a run can tell the glasses apart. A method that depends on it
  breaks the moment a glass is not painted, which is always, outside this
  simulator. That is why it is not used.

### Real glass

No. Real glass has no colour of its own to look for.

---

## 8. A trained segmentation model

Longer treatment: [mask models](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#12-mask-models) and
[promptable segmenters](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#13-promptable-segmenters-the-segment-anything-family),
with the licence position on each in
[licences and platforms](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/06_licences-and-platforms.md#21-for-finding-objects).
What this step needs is *instance* masks — one outline per glass, not one
outline for all the glass in the picture — and the difference is set out in
[four answers, and which one you need](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/01_overview.md#1-four-answers-and-which-one-you-need).

### The idea

A **segmentation model** is a neural network that has learned to outline
objects in a colour picture. It is shown a picture and draws a mask around
every glass in it.

### The options

- [Segment Anything](https://github.com/facebookresearch/segment-anything)
  outlines objects with no training at all, which makes it a good first try.
  It is heavy, and it needs a hint of where to look.
- A smaller [YOLO segmentation model](https://docs.ultralytics.com/tasks/segment/),
  or [Detectron2](https://github.com/facebookresearch/detectron2), trained on a
  few hundred labelled pictures, is faster and steadier in one kitchen. Note
  that Ultralytics YOLO is AGPL-3.0 licensed, which is a problem for a
  commercial product; `implementation-notes.md` names alternatives.

### Good

- **It is what a real cell would use**, for painted and see-through glasses
  alike.
- It copes with reflections far better than anything geometric.
- It drops straight in, because the rest of the project only needs a mask.

### Bad

- It needs labelled pictures, and a way to train on them.
- It goes out of date when the glassware changes.
- When it fails, it cannot say why. Nobody can read the reason off a log line.

### Real glass

Yes. This is the main reason to use it.

---

## 9. The patch with no depth in it

Longer treatment: [the depth hole, for glass and
chrome](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#17-the-depth-hole-for-glass-and-chrome).
Worth knowing that the reference work behind it —
[Lysenkov, Eruhimov and Bradski, RSS 2012](https://roboticsproceedings.org/rss08/p35.html) —
deliberately used the depth sensor's *failure* as the thing it measured, and
that the last of the five jobs it cannot do is the one that would bite here:
many cameras now fill in missing depth by default, which quietly destroys the
signal.

### The idea

This is what the project used to do, when the glasses were treated as really
see-through. A real depth camera gets nothing back from glass, so a glass shows
up in the depth picture as a glass-shaped hole: a patch of pixels with no
distance, where everything else has one. Treat that hole as the glass.

### Good

- **The hardest thing about glass becomes the measurement** instead of the
  obstacle.
- Nothing has to be trained.

### Bad

- **Gazebo cannot show it.** The simulator's depth camera measures a glass as
  if it were painted wood, so the hole never appears. The project had to fake
  it, and the step 1 document tells that story under *What went wrong here*.
- **The outline depends on the scene.** Reflections, bright spots, and one
  glass seen through another all break it. The simulator never showed this.

### Real glass

Yes. It is the honest answer if the opacity assumption is dropped.

---

## 10. Depth completion

Longer treatment: [transparent and shiny
objects](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#17-transparent-and-shiny-objects), which
tracks the four projects in this family and their licences. Two are abandoned,
one is non-commercial, and one — ReMake, MIT, 2026 — is the usable recent
option.

### The idea

A model trained on see-through objects looks at the colour picture, and at the
depth picture with the glass-shaped hole in it, and fills the hole with a
sensible guess. The result is a depth picture that looks as if the glass were
opaque. [ClearGrasp](https://sites.google.com/view/cleargrasp),
[TransCG](https://github.com/Galaxies99/TransCG) and
[DREDS](https://github.com/PKU-EPIC/DREDS) do this.

### Good

- On real glass, everything written for opaque objects starts working again,
  including today's "points above the table".
- It is the right move if what you want is a **point cloud**, a cloud of 3D
  dots on the glass's surface. That is what the grasp networks in
  [`step4-approaches.md`](step4-approaches.md) need.

### Bad

- This project never wanted a point cloud. It wants an outline, and a distance
  it already knows. Filling in depth to get there is a long way round.
- It is a trained model, with the same costs as approach 8.

### Real glass

Yes. It exists for real glass.

---

## 11. Polarised light

Longer treatment: [thermal, polarisation and the
rest](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#32-thermal-polarisation-and-the-rest), which is blunter
than this section is: polarisation imaging is frequently suggested for glass,
and there is essentially no open-source work behind the suggestion.

### The idea

Light reflected off glass changes its **polarisation**, the direction the
light waves swing in. A polarisation camera measures that, so it sees a glass
where an ordinary camera sees almost nothing. Factories use it to inspect
glass.

### Good

- It is the one idea here that is physically different from the others, and it
  works on real glass without any training.

### Bad

- It needs a camera this cell does not have.
- Gazebo does not simulate polarisation, so it could not even be tried here.

### Real glass

Yes.

---

## 12. Ask the simulator

Longer treatment: [use the simulator's ground truth — for scoring, never for
acting](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/07_making-it-work.md#1-how-to-tell-whether-it-is-working), which
draws the line this project draws. The ground truth may be read by the report
and never by the robot, and the moment any code path the robot runs reads it,
every number produced afterwards is meaningless.

### The idea

Read each glass's true position straight out of Gazebo.

### Why it is listed

Only to rule it out. It is the one method that would certainly work, and it
would make the project worthless. The problem statement forbids the arm from
reading the simulator's state, because a method that depends on it can never be
moved to a real cell.

---

## All of them side by side

For the first group, and today's method:

| Method | Finds where | Measures shape | Helps short glasses | Works on real glass | New hardware |
| --- | --- | --- | --- | --- | --- |
| 0. Wrist camera from above (today) | yes, about 30 mm out | no | finds them, cannot measure them | no | none |
| 0. Same, with 3D points and a circle | yes, should be much closer | height only | finds them, cannot measure them | no | none |
| 1. Fixed camera above | yes, one picture | height only | finds them, cannot measure them | no | one camera |
| 2. Fixed camera at the side | yes, with two cameras | **yes, full profile** | **yes** | yes, with a lit panel | one or two cameras |
| 3. Feeling with the fingers | no, needs a rough position | yes, slowly | no | yes | none |
| 4. Flat lidar | **yes, very accurate** | foot width only | finds them well | no | one or two lidars |
| 5. Fingertip proximity sensors | no, only refines | edges near the grip | no | capacitive: yes | sensors in the pads |
| 6. Force plate | one glass at a time | no | one at a time | yes | load cells |

For the second group, each row replaces only the "which pixels are a glass"
decision:

| Method | Works in this cell | Works on real glass | Needs training | New hardware |
| --- | --- | --- | --- | --- |
| 0. Points above the table (today) | yes | no | no | none |
| 7. Colour | yes, only because of the paint | no | no | none |
| 8. Segmentation model | yes | **yes** | yes | none |
| 9. The patch with no depth | not in Gazebo | **yes** | no | none |
| 10. Depth completion | not needed | **yes** | yes, or a download | none |
| 11. Polarised light | cannot be simulated | **yes** | no | a polarisation camera |
| 12. Ask the simulator | yes, and not allowed | no | no | none |

## Two things to keep in mind when choosing

**Finding and measuring are different jobs.** A method can be very good at one
and useless at the other. The lidar finds a glass to a millimetre, but cannot
see a stem. Touch measures a stem exactly, but cannot find a glass. A good
answer is often two methods: one to find, one to measure.

**Short glasses fail for two reasons, not one.** One reason is that the camera
cannot get low enough to see the foot. Approach 2 fixes that. The other is that
the gripper cannot hold a glass lower than about 50 mm, and must not hold it
above half its own height. A glass shorter than about 120 mm has no room left
between the two. No way of finding or measuring changes that. It needs a
different way of gripping, a slimmer gripper, or no glasses that short. That is
listed under *Decisions still open* in the
[problem statement](../problem-statement.md).

← [Step 1 — finding the glasses](step1-finding-the-glasses.md)
