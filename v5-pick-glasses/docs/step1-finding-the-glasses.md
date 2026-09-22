# Step 1 — finding the glasses

The arm starts by taking one picture from above, 45 cm over the table. It comes
away with a position for each glass and the width of its footprint. Nothing
else — and the things it deliberately does not learn here matter as much as the
things it does.

Code: `glasses/detect.py`, and `_survey()` in `task.py`.

## The depth camera sees nothing where the glass is

An RGB-D camera works by measuring how far away each pixel is. Most of them do
it by projecting a pattern of infrared light and watching where it lands.

Point one at a drinking glass and almost none of that light comes back. Some
goes straight through, some is bent sideways by the curved wall, and a little
scatters off at an angle that misses the sensor. The result is that the depth
image has a **hole** exactly the shape of the glass, while the colour image
shows the glass perfectly well.

This is the single most common complaint about using depth cameras with
glassware, and it is usually treated as the obstacle to get past.

It is better treated as the measurement.

```python
missing = ~np.isfinite(depth) | (depth <= 0.0)
lit = rgb.max(axis=2) > 25
return missing & lit
```

A pixel where the depth is missing but the colour camera can see something is a
pixel looking through a transparent object. That is what a glass is.

The second line matters. A hole on its own is not enough — the depth image is
also blank over the far wall, over anything beyond the camera's 3 m range, and
around the edges of the frame. Requiring that *something is visible there*
throws all of that away.

## Why this is honest rather than convenient

It would be fair to ask whether this only works because it is a simulator.

It is the reverse. A simulated depth sensor is configured to return nothing
where it cannot get a reading, which is precisely what a real one does with
glass. Building the pipeline on the hole means the code meets the same
difficulty a real cell would, and the piece that would have to change on real
hardware is one function.

What would change is the *quality* of the hole. In a real kitchen there are
reflections, one glass seen through another, and highlights that confuse the
outline. The production answer there is a segmentation model, and
`glass_mask()` is the function it would be called from. Everything downstream
takes a boolean mask and does not care where it came from.

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

## What the arm does next

The glasses are sorted by distance from the robot base and the nearest one is
taken first, so the arm never reaches over one glass for another it could have
taken first. Then every *other* glass is handed to MoveIt as a cylinder, and
the target is left out — because the planner will not let the fingers enter a
space it believes is solid.

→ [Step 2 — measuring one](step2-measuring-one.md)
