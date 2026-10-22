# Problem 2 — the shared test bench

All six solutions are tested on this bench. They get the same scenes, the same
pictures and the same scorecard. [The examiner
document](../docs/the-examiner.md) explains why. This page
only says which file holds which part.

Nothing here imports a solution. A solution imports from here.

- `render.py` — the numbered scenes, each with four to six glasses of one kind,
  and depth pictures of them from any camera pose. It stands in for Gazebo.
  Scenes from one number upwards are for testing only. No training may use them.
- `data.py` — what a solution is handed: the three overlapping survey stations,
  their pictures, and the training labels. It also keeps the id images, which
  say which glass owns each pixel. A solution never sees those while answering.
- `pictures.py` — dresses a depth picture as a colour photo. The borrowed models
  in solutions 3 to 6 were trained on photos, and this cell has no camera that
  takes one.
- `masks_to_glasses.py` — turns one mask into a place on the table and a rough
  width. Every solution calls it. So a difference in the scorecard comes from
  the mask, never from what was done with it. It also says whether a mask
  reaches the edge of its picture. A glass cut by the frame shows only part of
  its footprint, and a solution that refuses on width needs to know this. What
  to do about it is up to each solution.
- `marking.py` — the survey itself. It asks a solution about each station's
  picture, decides which station to believe where two overlap, and writes the
  answer in one format. Each solution's `run.py` calls it. It is not called
  `run.py`, because each solution's runner already has that name and the two
  would clash.
- `scoring.py` — the scorecard. It matches each report to a real glass. It
  measures how far the place was from the truth. It measures how much of the
  real glass the mask covered, and how much of the mask was not that glass, by
  kind of glass.
- `floor.py` — the best answer any method could give. It runs the renderer's
  own masks through the same steps and marking. Every result can be read
  against it.
- `device.py` — which processor the work runs on.

## This bench's camera is simpler than the cell's, on purpose

Read this before you compare a number here with one from the cell. The cell's
wrist camera is an **Intel RealSense D405**. It sees 87 degrees across and is
read at 640 by 360 pixels. This bench uses a simpler lens: 60 degrees across at
320 by 240. It also keeps its own margin at the picture's edge, rather than
using the cell's gripper.

There are two reasons.

First, every result in this problem was measured through this lens and margin.
Changing either would change every picture, mask, width and score already
committed. Nothing would be comparable any more.

Second, and more important, **none of it changes the question this problem
asks.** The question is how well six methods find glasses in a picture. [The
examiner](../docs/the-examiner.md) gives all six the
*same* picture. A wider lens would make every method's job harder in the same
way. The ranking is what matters, so problem 2 does not need the cell's camera.

But do not assume this is the cell's camera. It is a simpler stand-in. Where a
document compares a number here with one from the cell, it says which camera it
came from. The real camera is described in [the cell](../../01-rack-one-glass/docs/the-cell.md).
