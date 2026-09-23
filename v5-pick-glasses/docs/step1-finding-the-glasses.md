# Step 1 — finding the glasses

The run starts with the arm knowing nothing about the table in front of it. It
does not know how many glasses are on it. It does not know where they are, or
how big any of them is. The [problem statement](../problem-statement.md) does
not let anyone tell it. Everything the arm uses from here on, it has to have
measured itself. This step is where that begins.

What this step produces is small, on purpose. For each glass it gives a
position on the table and a rough width of the footprint. It gives nothing
about height and nothing about shape. From directly above, a tall glass and a
short one look almost the same, and a stem is hidden under the bowl. Height and
shape belong to step 2, which looks from the side. Asking for them here would
mean guessing.

Finding the glasses at all rests on one assumption, and it is the first thing
to say. The glasses in this cell are **opaque**. Each one is painted a solid
colour, and the camera sees it as plainly as it sees the table. That is written
in the problem statement as an assumption, not as a fact about glassware. Real
glass defeats a depth camera completely. The last two sections of this document
say what changes when the assumption is dropped.

Code: `glasses/detect.py`, and `_survey()` in `task.py`.

What follows, in order:

- the step in pseudocode, and the libraries it uses
- what the camera gives the arm
- how a glass is told apart from the table
- how it is told apart from the rack and from the arm's own gripper
- how a patch of pixels becomes a place
- what this step refuses to guess at
- why one picture is not enough
- what went wrong when this was first run
- where the method can still fail
- how else it could have been done
- what the arm does next

## The step in pseudocode

Each line says who does the work: **ours** means code in this repo, and a named
library means the work is not ours.

```text
work out where to stand the camera
    ask the camera what lens it has             ROS 2: /camera_info topic
    tile the glass zone with overlapping        ours: arm/dimensions.py
      stations                                    survey_stations()

for each station:
    for each of the two camera positions:
        move the wrist there                    MoveIt 2: plan a path round
                                                  the table and the rack
                                                ros2_control: drive the joints
        wait for one RGB-D frame                Gazebo: simulates the sensor
                                                ros_gz_bridge: Gazebo -> ROS 2
                                                cv_bridge: ROS image -> array
        read where the camera really was        tf2: the wrist pose, as a
                                                  4x4 into the world frame
        mask = points above the table top       ours: glasses/detect.py
                                                  standing_on_the_table()
        patches = flood fill the mask           ours: detect.py _label()
        sightings = lay each patch's rays       ours: detect.py find_glasses()
          down on the table                       and View.to_world()

    placed = pair the two sets of sightings,    ours: detect.py
      and solve for how high each glass is        where_they_stand()

merge sightings of the same glass across        ours: detect.py
  stations                                        merge_sightings()
sort by distance from the arm's base            ours: task.py run()
hand every glass but the target to the          MoveIt 2: planning scene
  planner as a cylinder
```

### What each library gives this step

| Piece | Ours or a library | What it does here |
| --- | --- | --- |
| `glasses/detect.py` | ours | every decision in this step: what counts as standing on the table, what counts as one glass, and where it stands |
| `task.py` | ours | the order things happen in, and nothing else |
| `arm/dimensions.py` | ours | where the stations go, worked out from the lens |
| [ROS 2 Jazzy](https://docs.ros.org/en/jazzy/) | library | the message plumbing: topics for the images and the lens, and the service calls to the planner |
| [Gazebo Harmonic](https://gazebosim.org/docs/harmonic/) | library | simulates the RGB-D camera and the physics of the cell |
| [ros_gz_bridge](https://github.com/gazebosim/ros_gz) | library | carries Gazebo's images and camera info onto ROS 2 topics |
| [cv_bridge](https://github.com/ros-perception/vision_opencv) | library | turns a ROS image message into a NumPy array |
| [tf2](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Tf2.html) | library | where the camera was when it took the picture, in world coordinates |
| [MoveIt 2](https://moveit.picknik.ai/main/index.html) | library | plans a path to each station that misses the table, the rack and the other glasses |
| [ros2_control](https://control.ros.org/jazzy/index.html) | library | runs that path on the arm's joints |
| [NumPy](https://numpy.org/) | library | the mask arithmetic and the ray projection, as whole-array operations |
| [OpenCV](https://github.com/opencv/opencv) | library | used for the rack's ArUco marker, not for finding glasses |

Worth noticing what is *not* in that list. No neural network, no trained model,
and no point cloud library. Finding a glass here is a height comparison and a
line-plane intersection, both of which are NumPy one-liners.

## What the camera gives the arm

The wrist camera is an RGB-D camera. It returns two pictures at once. One is
the ordinary colour picture. The other is a **depth picture**. The depth
picture is the same size as the colour one, but each pixel holds a distance
instead of a colour. The distance is how far the camera was from whatever that
pixel was pointing at. A pixel looking at the table a third of a metre below
holds 0.33.

A distance on its own is not a place. To turn it into one, the arm has to know
where the camera was and which way it was facing. It knows both. It put the
camera there itself, and it can read its own joints.

With that, any pixel becomes a point in the room. The pixel says which
direction the camera was looking in. The distance says how far to travel along
that direction. The camera's pose says where that direction starts.

## Telling a glass from the table

Once every pixel is a point in the room, finding a glass is almost too simple
to write down. The table top is at a known height. A point above that height is
something standing on the table. A point at that height is the table.

```python
standing = np.isfinite(depth) & (depth > 0.0) & (height > table_z + clearance)
```

`clearance` is five millimetres. That is comfortably more than the wobble on a
depth reading, and far less than the shortest glass. Nothing real falls between
the two.

The first two tests drop pixels that have no distance at all. The sky is one.
So is anything past the camera's three-metre range. A pixel with no distance
cannot be turned into a point, so it cannot be judged.

## Telling a glass from the rack, and from the arm itself

"Anything standing on the table" is honest and too generous. The rack stands on
the table. So does the arm's own gripper, which often hangs into the bottom of
its own pictures. Three things keep both out of the answer.

**The camera is only ever pointed where the glasses are.** The glasses are put
out inside one rectangle of the table, `GLASS_ZONE` in `rack/layout.py`. The
rack stands on the other side of the arm. The glasses sit at y between −440 and
−80 mm, and the rack sits at about y = +350 mm. The survey tiles its stations
across that rectangle and nowhere else. Each picture covers about 520 by 390 mm
from survey height, and the station closest to the rack still stops around
280 mm short of it. The rack is therefore not in a survey picture at all.

That is the real reason the rack is never taken for a glass in the survey: the
arm does not look at it. It is a fact about how this cell is laid out, not
about what a glass looks like, and it is written down in exactly two places —
`GLASS_ZONE`, and `random_rack_pose()` in `rack/build.py`, which draws the
rack's position from a band on the far side of the arm. Put the rack in among
the glasses and this step would report it as a glass.

**Nothing taller than the tallest glass the cell handles.** That is 260 mm, a
limit of the cell written down once. It removes the gripper, the arm, and
anything else reaching down through the frame. It does not remove the rack. The
rack is only 55 mm tall, so it passes this test easily, which is why the rack
is handled by where the camera looks and by the bound below.

**Only what lies at roughly the distance the arm stood off at.** This bound is
for the side-on view in step 2 rather than for the survey. The arm chose how
far back to stand, so it knows how far away the glass ought to be. Keeping only
the pixels in a band around that distance drops the rack, and drops the other
glasses standing behind the one it came to measure. It is not a guess about the
scene. It is the arm remembering what it did.

That bound was added after a real failure. On the first run with opaque
glasses, the arm measured a glass as 78 mm tall that is really 145 mm. What it
had actually found, and measured, was the rack standing behind it.

None of the three bounds is a fact about a glass. That matters. A number
describing one particular glass is the one thing this project may not hold.

## From a patch of pixels to a place on the table

`_label()` groups the mask into patches with a flood fill. There are a few
glasses in a 320×240 frame, so the simple version is fast and brings in no new
dependency. Anything under 150 pixels is thrown away as a speck.

Turning a patch into a position is the interesting part. The one thing the
camera cannot give here is a distance to the glass. The glass has no depth
reading of its own that the arm trusts, so the position has to come from
geometry.

A pixel is not a point. It is a **ray**. Everything along that line projects to
the same pixel. Saying which height the thing is at picks one point off the
ray. Here the height is known, because the glass stands on the table and the
table is at 75 cm.

```python
direction = [(column - cx) / fx, (row - cy) / fy, 1.0]
ray = camera_rotation @ direction
point = eye + ray * ((z - eye[2]) / ray[2])
```

That is `View.to_world()`. The table plane does the job the distance would have
done.

The footprint width is measured the same way. Both edges of the patch are laid
down on the table, and the distance between them is taken there. It is *not* a
pixel count scaled by a constant. The same glass photographed from twice the
height covers half as many pixels and is still the same glass.

One detail is worth half a millimetre. The edges are taken half a pixel outside
the outermost glass pixels. A pixel's position is its centre, so the outside of
the leftmost pixel is half a pixel further left. Without that, every width
comes out one pixel short. That is a bias, not noise.

## What this step deliberately does not produce

**Not the height.** From directly above, a glass is seen end-on. A 240 mm flute
and a 90 mm tumbler present the same silhouette. No amount of care with the
overhead picture will separate them. `Detection` has no height field at all,
and anything needing one gets it from step 2.

**Not the kind.** A stem is completely hidden under the bowl when seen from
above. Classifying here would mean guessing, and a glass given the wrong rule
is a glass held in the wrong place.

**Not a precise width.** The footprint width is a rough figure. It is used to
tell MoveIt roughly where the glass is, so the planner keeps the arm out of it.
The width the fingers are actually set to comes from step 2, and is a different
number measured a different way.

A `Detection` is therefore three fields: a name, a position, and a rough width.
Being this sparse is the point. Everything the arm decides about a glass is
decided after it has looked at the glass properly.

## One picture cannot say how far away a glass is

![One look against two](../images/one-look-two-looks.png)

Laying a ray down on the table is exact for anything lying flat *on* the table.
That is why the marker on the rack is found perfectly every run: it is printed
flat on the rack's base. A glass is not flat. From overhead the camera sees the
widest part of the glass, standing some way above the table. Following that ray
down to the table carries it past where the glass really is, out and away from
the point directly under the camera. The further off to one side the glass is,
the worse it gets. Measured against a glass whose true position was known, one
standing 157 mm from the camera was reported 244 mm away.

The arm cannot correct this from one picture. The correction needs the glass's
height, and the height is exactly what an overhead view cannot see. It can
correct it from two pictures. That same unknown height decides how far the
glass appears to shift when the camera steps sideways by a known amount. So the
shift measures the height. Step sideways by `d`, and a glass lying flat on the
table appears to move by `d` divided by however much it was stretched. Each
survey station therefore takes two pictures a known distance apart, and
`where_they_stand()` works the rest out.

Two things follow. Stations are tiled over the part of the table that *both*
pictures of a pair cover, not over one picture. A glass caught in only one of
the pair cannot be placed at all, and is better left to the next station. And a
glass so short that it barely leans reads as having moved exactly as far as the
camera did. The arithmetic turns that into a glass below the table. That is not
a different glass. It is one with almost no lean to measure, so it is taken as
standing on the table rather than thrown away.

## What went wrong here

For most of this project's life the glasses were treated as though they were
really see-through. The history is worth keeping, because it explains a large
part of the code that is no longer there.

**The arm used to look for what the camera could not measure.** A real depth
camera gets nothing back through glass. The light goes straight through. So on
real glassware, the depth picture arrives with a glass-shaped patch of pixels
that carry no distance at all, while every other object in the picture has one.
The old design treated that empty patch as the measurement rather than as a
problem. A pixel with no distance, but with something visible in the colour
picture, was taken to be a pixel looking through a glass.

**The simulator would not produce that empty patch.** Gazebo's depth camera
measures a glass as though it were painted wood. Its renderer applies
transparency to colour and not to depth. So the depth picture arriving at the
perception code had nothing missing from it anywhere. The mask came back empty,
and every run ended having found nothing. The fix at the time was to make the
empty patch by hand. A second camera reported which pixels were glass, and the
wrist camera erased the depth at those pixels before handing the picture on.

**Then the sky was read as a glass.** Past the edge of the table, a camera
looking level sees nothing at all, so those pixels have no distance either. The
only thing separating them from a glass was whether the colour picture showed
anything there. The background had been set dark for exactly that reason, but
not dark enough. The simulator writes colours out gamma encoded, so a nearly
black two per cent grey arrives as 41 out of 255, and that counts as something
visible. The whole horizon read as one glass 346 mm across.

All of that is gone. Once the glasses are assumed opaque, the camera simply
sees them. Every one of those faults goes with the assumption. There is nothing
to manufacture any more, and a pixel with no distance is dropped rather than
argued about. What replaced it brought one fault of its own — the rack being
measured as a glass — which the bounds above now prevent.

## Where this approach can fail

The method is simple, and it is worth being exact about what it assumes. Each
of these is a real way it breaks.

**Anything else standing on the table is reported as a glass.** The test is
only "does this stand above the table, and is it shorter than 260 mm". A mug, a
jug, a bottle, a folded cloth and a spoon all pass it. Nothing anywhere in this
pipeline asks "is this a glass?". Step 3 asks a narrower question — "which of
my four kinds does this outline match?" — and an object matching none of them
is refused and left standing, with a line in the report. So an unknown object
costs a wasted trip round it rather than a broken run. An unknown object shaped
enough like a tumbler would be picked up and racked.

**Two objects touching read as one.** The flood fill cannot separate them, so
the survey reports a single wide patch. Step 2 then measures whatever is in the
middle of its picture, which is a coin toss between the two. Spacing the
glasses is currently the only defence.

**A glass outside the surveyed rectangle is never seen.** The stations tile
`GLASS_ZONE` and nothing else. A glass pushed 100 mm past its edge is not
missed by the detector. It is never photographed.

**A glass over 260 mm tall is dropped in silence.** That is the cell's limit,
and it is deliberate, but it means an unusually tall glass is treated the same
way as the arm's own gripper.

**A glass caught in only one picture of a pair cannot be placed.** The
stations overlap so that another station usually catches it in both. A glass
that never lands inside the shared part of any pair is never placed.

**A glass lying on its side is not handled.** Everything here assumes a glass
stands upright on the table. A fallen glass is still found as something
standing above the table, but its position and width mean nothing, and step 2
measures an outline no rule can use.

**Real glass defeats the whole step.** This is the big one. Drop the opacity
assumption and the depth picture has no glass in it to find. The next section
is about what to do then.

**Real depth cameras have failures the simulator does not.** A very dark or
shiny surface can return no depth on real hardware even when it is opaque, and
sunlight washes out the projected pattern most of these cameras rely on. In
Gazebo the depth picture is perfect, so none of this shows up here.

## Other ways to find a glass

The method above is chosen for opaque glasses, and it is the weakest part of
the project to lean on. The assumption underneath it is the first one a real
kitchen would take away. So this section comes in two halves: other ways to
find an opaque object, and what to do when the glasses really are glass.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **Points above the table** | anything standing higher than the table top | NumPy, in `glasses/detect.py` | good, and in use |
| **Colour** | finds the glass by the colour it is painted | [OpenCV](https://github.com/opencv/opencv) | works here, and only here |
| **A trained segmentation model** | learns to outline glass in the colour picture | [Segment Anything](https://github.com/facebookresearch/segment-anything), [Detectron2](https://github.com/facebookresearch/detectron2), [Ultralytics YOLO](https://docs.ultralytics.com/) | what a real cell would use |
| **The patch with no depth in it** | treats a real sensor's failure as the measurement | [OpenCV](https://github.com/opencv/opencv) | the answer if the assumption is dropped |
| **Depth completion for glass** | fills in the depth the glass did not return | [ClearGrasp](https://sites.google.com/view/cleargrasp), [TransCG](https://github.com/Galaxies99/TransCG), [DREDS](https://github.com/PKU-EPIC/DREDS) | for real glass, and only worth it to feed a point cloud |
| **Polarised light** | glass changes the polarisation of reflected light | a polarisation camera, then OpenCV | real, and needs hardware this cell has not got |
| **Ask the simulator** | read the glass's true position out of Gazebo | [Gazebo](https://gazebosim.org/) directly | cheating, and it teaches nothing |

**Points above the table** is what is used here. It needs no training and no
model to ship. It holds nothing about any particular glass, so it works on a
glass the project has never seen. It also fails honestly: a pixel it cannot
place, it drops. Its weaknesses are the two named above — the opacity
assumption, and its inability to tell two touching objects apart.

**Colour** would work perfectly in this cell and nowhere else. The glasses are
painted, so a colour threshold would find them, and it is tempting because it
is three lines long. It is left alone for one reason. The paint exists so that
a *person* can follow a run. A pipeline that depended on it would break the
moment a glass was not painted, which is to say always, outside this simulator.

**A trained segmentation model** is what a real cell would use, for opaque and
see-through glasses alike. The project is arranged so it would drop straight
in: one function decides which pixels are a glass, and everything downstream
takes a plain boolean mask.
[Segment Anything](https://github.com/facebookresearch/segment-anything) will
outline a glass with no training at all, which makes it a good first try,
though it is heavy and needs prompting. A smaller
[YOLO segmentation model](https://docs.ultralytics.com/tasks/segment/) trained
on a few hundred labelled pictures would be faster and steadier in one kitchen.
The cost is needing those pictures, and going stale when the glassware changes.
Either one handles reflections far better than anything geometric. Either one
also brings a training set, a training pipeline, and a component that fails in
ways nobody can read off a log line.

**The patch with no depth in it** is the honest answer if the opacity
assumption is dropped, and it is what this project used to do. The section
above explains how it worked and why it went. On real hardware it has a real
virtue: the hardest property of the object becomes the measurement rather than
the obstacle, and nothing has to be trained. It has a real weakness the
simulator never showed. The quality of the outline depends entirely on the
scene. Reflections, highlights, and one glass seen through another all break
it.

**Depth completion** guesses the surface the sensor could not see.
[ClearGrasp](https://sites.google.com/view/cleargrasp) and the work after it
turn a real glass into an ordinary point cloud, so everything written for
opaque objects starts working again. It is the right move if what you want is a
point cloud, because it unlocks the off-the-shelf grasp planners discussed in
step 4. It is the wrong move here even on real glass. This project never wanted
a point cloud. It wants a silhouette, and a distance it already knows.

**Polarisation** is the one physically different idea on the list. Glass
changes how reflected light is polarised, so a polarisation camera sees a glass
where an ordinary camera does not. Industrial inspection uses it for exactly
this. It needs hardware this cell has not got, and Gazebo does not model it, so
it could not be tried here even in principle.

**Reading poses out of the simulator** is on the list to be dismissed. It is
the one option that would certainly work, and it would make the project
worthless. A pipeline that depends on ground truth cannot be moved to a real
cell at all.

## What the arm does next

The glasses are sorted by distance from the robot base, and the nearest one is
taken first. That way the arm never reaches over one glass for another it could
have taken first. Then every *other* glass is handed to MoveIt as a cylinder,
and the target is left out — because the planner will not let the fingers enter
a space it believes is solid.

→ [Step 2 — measuring one](step2-measuring-one.md)
