# Step 1 — finding the glasses

The run starts with the arm knowing nothing about the table in front of it. It
does not know how many glasses are on it, where they are, or how big any of
them is, and the [problem statement](../problem-statement.md) does not let it
be told: everything it uses from here on it has to have measured. This step is
where that begins.

What it has to produce is modest and deliberately so — a position on the table
for each glass, and roughly how wide each one's footprint is. What it must not
produce is anything about height or shape, because from directly above a tall
glass and a short one look almost identical and a stem is invisible. Those
belong to step 2, which looks from the side, and asking for them here would
mean guessing.

Finding them at all rests on an assumption, and it is the first thing to say.
The glasses in this cell are **opaque** — each is painted a solid colour, and
the camera sees it as plainly as it sees the table. That is written down in
the problem statement as an assumption rather than a fact about glassware,
because real glass defeats a depth camera completely, and the last section of
this document is about what changes when the assumption is dropped.

Code: `glasses/detect.py`, and `_survey()` in `task.py`.

Below: how a picture becomes places in the room, what keeps the rack and the
arm's own fingers out of the answer, how a patch of pixels becomes one glass,
what this step refuses to guess at, why one look from above is not enough on
its own, what went wrong when this was first run, how else it could have been
done, and what the arm does with the answer.

## A picture of distances, turned into places in the room

The wrist camera is an RGB-D camera, which means it returns two pictures at
once. One is the ordinary colour picture. The other is a **depth picture**: an
image the same size, where each pixel holds a distance instead of a colour —
how far the camera was from whatever that pixel was pointing at. A pixel
looking at the table top a third of a metre away holds 0.33.

A distance on its own is not a place. What turns it into one is knowing where
the camera was and which way it was facing, and the arm knows both, because it
put the camera there itself and can read its own joints. With those, any pixel
becomes a point in the room: the pixel says which direction the camera was
looking in, the distance says how far along that direction to go, and the
camera's own pose says where that direction starts and where it points.

Once every pixel is a point in the room, finding a glass is almost too simple
to write down. The table top is a known height. Anything whose points sit
above that height is standing on the table, and anything at that height is the
table.

```python
standing = np.isfinite(depth) & (depth > 0.0) & (height > table_z + clearance)
```

`clearance` is five millimetres, which is comfortably more than the wobble on
a depth reading and far less than the shortest glass, so nothing real falls
between the two. The first two tests drop pixels that have no distance at all
— sky, and anything past the camera's three-metre range — because a pixel with
no distance cannot be turned into a point and so cannot be judged.

## Keeping the rack and the arm out of the answer

"Anything standing on the table" is honest and slightly too generous. The rack
stands on the table. So does the arm's own gripper, which is frequently in the
bottom of its own pictures. Both would be found, and on the first run after
this was written the arm measured a glass 78 mm tall that is really 145,
because what it had actually found was the rack.

Two bounds fix that, and neither of them is a fact about glasses — which
matters, because a number describing a particular glass is the one thing this
project may not hold.

**Nothing taller than the tallest glass the cell handles.** That is a limit of
the cell, written down once, and it removes the gripper, the arm and anything
else that reaches up through the frame.

**Only what lies at roughly the distance the arm stood off at.** This one is
for the side-on view in step 2 rather than for the survey. The arm chose how
far away to stand, so it knows how far away the glass ought to be, and keeping
only the pixels in a band around that distance drops the rack and the other
glasses standing behind the one it came to measure. It is not a guess about
the scene; it is the arm remembering what it did.

## From a blob to a place on the table

`_label()` groups the mask into blobs with a flood fill — a few glasses in a
320×240 frame, so the simple version is fast and brings in no dependency.
Anything under 150 pixels is thrown away as a speck.

Turning a blob into a position is the interesting part, because the one thing
the camera cannot give here is a distance. The glass has no depth reading; that
is how it was found in the first place.

So the position comes from geometry instead. A pixel is not a point, it is a
**ray**: everything along that line projects to the same pixel. Saying which
height the thing is at picks one point off the ray, and here the height is
known, because the glass is standing on the table and the table is at 75 cm.

```python
direction = [(column - cx) / fx, (row - cy) / fy, 1.0]
ray = camera_rotation @ direction
point = eye + ray * ((z - eye[2]) / ray[2])
```

That is `View.to_world()`. The plane does the job the missing depth reading
would have done.

The footprint width is measured the same way: both edges of the blob are put on
the table and the distance between them is taken there. It is *not* a pixel
count scaled by a constant, because the same glass photographed from twice the
height covers half as many pixels and is still the same glass.

One detail that is worth half a millimetre: the edges are taken half a pixel
outside the outermost glass pixels. A pixel's position is its centre, so the
outside of the leftmost pixel is half a pixel further left. Without that, every
width comes out one pixel short — a bias, not noise.

## What this step deliberately does not produce

**Not the height.** From directly above, a glass is seen end-on. A 240 mm flute
and a 90 mm tumbler present the same silhouette, and no amount of care with the
overhead image will separate them. So `Detection` has no height field at all,
and anything that needs one gets it from step 2.

**Not the kind.** For the same reason, and worse: a stem is entirely hidden
under the bowl when seen from above. Classifying here would mean guessing, and
a glass given the wrong rule is a glass held in the wrong place.

**Not a precise width.** The footprint width is a rough figure used to tell
MoveIt roughly where the glass is, so that the planner keeps the arm out of it.
The width that the fingers are actually set to comes from step 2 and is a
different number measured a different way.

A `Detection` is therefore three fields: a name, a position, and a rough width.
Being this sparse is the point. Everything the arm decides about a glass is
decided after it has looked at it properly.

## One look cannot say how far away a glass is

![One look against two](../images/one-look-two-looks.png)

The projection above is exact for anything lying *on* the table, which is why
the marker on the rack is found perfectly every run — it is printed flat on
the rack's base. A glass is not flat. What the camera sees from overhead is
the widest part of the glass, standing some way above the table, and following
that ray down to the table carries it past where the glass actually is, out
and away from the point directly under the camera. The further off to one side
the glass is, the worse it gets: measured against a glass whose true position
was known, one standing 157 mm from the camera was being reported 244 mm away.

The arm cannot correct for this from one picture, because the correction needs
the glass's height and the height is exactly what the overhead view cannot
see. It can correct for it from two. That same unknown height decides how far
the glass appears to shift when the camera steps sideways by a known amount,
so the shift measures it: step by `d`, and a glass laid down on the table
appears to move by `d` divided by however much it was stretched. The survey
therefore takes two pictures at each station, a known distance apart, and
`where_they_stand()` works the rest out.

Two things follow from that. Stations are tiled over the part of the table
that *both* pictures of a pair cover rather than over one picture, because a
glass caught in only one of them cannot be placed at all and is better left to
the next station. And a glass so short that it barely leans reads as having
moved exactly as far as the camera did, which the arithmetic turns into a
glass below the table; that is not a different glass, it is one with almost no
lean to measure, so it is taken as standing on the table rather than thrown
away.

## What went wrong here

For most of this project's life the glasses were treated as though they were
really see-through, and the history is worth keeping because it explains a
large part of the code that is no longer there.

**The arm used to look for a hole.** A real depth camera gets nothing back
through glass, so on real glassware the depth picture arrives with a
glass-shaped gap in it — a patch of pixels with no distance at all, where
every other object would have had one. That gap is what "the hole" meant. The
original design treated it as the measurement rather than the obstacle: a
pixel with no distance, but with something visible in the colour picture, is a
pixel looking through a glass.

**The simulator would not produce one.** Gazebo's depth camera measures a
glass as though it were painted wood — transparency is something its renderer
applies to colour and not to depth — so the picture arriving at the perception
had nothing missing from it anywhere, the mask came back empty, and every run
ended with nothing found. The fix at the time was to manufacture the hole: a
second camera reported which pixels were glass, and the wrist camera blanked
the depth at those pixels before handing the picture on, so that what left the
camera looked like what a real sensor would have produced.

**And then the sky became a glass.** Past the edge of the table a camera
looking level sees nothing at all, so those pixels have no distance either,
and the only thing separating them from a glass was whether the colour picture
showed something there. The background had been set dark for exactly that
reason, but not dark enough: the simulator writes colours out gamma encoded,
so a nearly black two per cent grey arrives as 41 out of 255, which counts as
something visible. The whole horizon read as a single glass 346 mm across.

All of that is gone. Once the glasses are assumed opaque the camera simply
sees them, and every one of those faults goes with the assumption: there is no
hole to manufacture, and a pixel with no distance is dropped rather than
argued about. What replaced it brought one fault of its own, the rack being
measured as a glass, which the two bounds above now prevent.

## Other ways to find a glass

The method above is chosen for opaque glasses and is the weakest part of the
project to lean on, because the assumption it rests on is the one a real
kitchen would take away first. So this section is in two halves: other ways to
find an opaque object, and what to do when the glasses really are glass.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **Points above the table** | anything standing higher than the table top | NumPy, in `glasses/detect.py` | good, and in use |
| **Colour** | finds the glass by the colour it is painted | [OpenCV](https://github.com/opencv/opencv) | works here, and only here |
| **A trained segmentation model** | learns to outline glass in the colour picture | [Segment Anything](https://github.com/facebookresearch/segment-anything), [Detectron2](https://github.com/facebookresearch/detectron2), [Ultralytics YOLO](https://docs.ultralytics.com/) | what a real cell would use |
| **The hole in the depth picture** | treats a real sensor's failure as the measurement | [OpenCV](https://github.com/opencv/opencv) | the answer if the assumption is dropped |
| **Depth completion for glass** | fills in the depth the glass did not return | [ClearGrasp](https://sites.google.com/view/cleargrasp), [TransCG](https://github.com/Galaxies99/TransCG), [DREDS](https://github.com/PKU-EPIC/DREDS) | for real glass, and only worth it to feed a point cloud |
| **Polarised light** | glass changes the polarisation of reflected light | a polarisation camera, then OpenCV | real, and needs hardware this cell has not got |
| **Ask the simulator** | read the glass's true position out of Gazebo | [Gazebo](https://gazebosim.org/) directly | cheating, and it teaches nothing |

**Points above the table, which is what is used here.** It needs no training,
no model to ship, and nothing about any particular glass; it works on a glass
the project has never seen, and it fails honestly, because a pixel it cannot
place it simply drops. Its weakness is the assumption underneath it, and a
second one worth naming: it cannot tell two touching objects apart, which is
why the side-on step has to pick the one in the middle of the picture.

**Colour** would work perfectly in this cell and nowhere else. The glasses are
painted, so a colour threshold would find them, and it is tempting because it
is three lines. It is left alone because the paint exists so that a *person*
can follow a run, and a pipeline that depends on it would break the moment a
glass was not painted — which is to say, always, outside this simulator.

**A trained segmentation model** is what a real cell would use, for opaque
glasses and see-through ones alike, and the project is arranged so that it
would drop straight in: one function decides which pixels are a glass, and
everything downstream takes a plain boolean mask.
[Segment Anything](https://github.com/facebookresearch/segment-anything) will
outline a glass with no training at all, which makes it a good first try,
though it is heavy and needs prompting; a smaller
[YOLO segmentation model](https://docs.ultralytics.com/tasks/segment/) trained
on a few hundred labelled pictures would be faster and steadier in one
kitchen, at the cost of needing those pictures and of going stale when the
glassware changes. Either handles reflections far better than anything
geometric, and either brings a training set, a training pipeline, and a thing
that fails in ways nobody can read off a log line.

**The hole** is the honest answer if the opacity assumption is dropped, and it
is what this project used to do — the section above explains how it worked and
why it went. On real hardware it has a real virtue: the hardest property of
the object becomes the measurement rather than the obstacle, and nothing has
to be trained. It has a real weakness too, which the simulator never showed,
because the quality of the hole depends entirely on the scene: reflections,
one glass seen through another, and highlights all break the outline.

**Depth completion** — [ClearGrasp](https://sites.google.com/view/cleargrasp)
and the work after it — guesses the surface the sensor could not see, so that
a real glass arrives as an ordinary point cloud and everything written for
opaque objects starts working. It is the right move if what you want is a
point cloud, because it unlocks the off-the-shelf grasp planners discussed in
step 4. It is the wrong move here even on real glass, because this project
never wanted a point cloud: it wants a silhouette and a distance it already
knows.

**Polarisation** is the one physically different idea on the list. Glass
changes how reflected light is polarised, so a polarisation camera sees it
where an ordinary camera does not, and it is used in industrial inspection for
exactly this. It needs hardware this cell has not got and is not modelled in
Gazebo, so it could not be tried here even in principle.

**Reading poses out of the simulator** is on the list to be dismissed. It is
the one option that would certainly work and would make the project
worthless, because a pipeline that depends on ground truth cannot be moved to
a real cell at all.

## What the arm does next

The glasses are sorted by distance from the robot base and the nearest one is
taken first, so the arm never reaches over one glass for another it could have
taken first. Then every *other* glass is handed to MoveIt as a cylinder, and
the target is left out — because the planner will not let the fingers enter a
space it believes is solid.

→ [Step 2 — measuring one](step2-measuring-one.md)
