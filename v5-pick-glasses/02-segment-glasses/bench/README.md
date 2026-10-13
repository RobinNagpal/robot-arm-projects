# Problem 2 — the shared test bench

Used by all six solutions in this folder, so that every one of them is tested on
the same scenes, is handed the same pictures, and is judged by the same
scorecard. That is the whole reason the bench exists: when the input and the
marking are the same for all six, a difference between their results belongs to
the method and to nothing else. [The bench
document](../../docs/02-segment-glasses/the-examiner.md) explains the contract;
this page only says which file holds which part of it.

Nothing here imports a solution. A solution imports from here.

- `render.py` — the numbered scenes, four to six glasses of one kind, and depth
  pictures of them from any camera pose. It stands in for Gazebo. Scenes from
  one number upwards are for testing only, and no training may draw from them.
- `data.py` — what a solution is actually handed: the three overlapping survey
  stations, the pictures taken from them, and the training labels. It also keeps
  the id images, which say which glass owns each pixel and which a solution
  never sees while answering.
- `pictures.py` — dresses a depth picture as the colour photograph a borrowed
  model expects, because the models in solutions 3 to 6 were trained on
  photographs and this cell has no camera that takes one.
- `masks_to_glasses.py` — turns one mask into a place on the table and a rough
  width. Every solution calls it, so a difference in the scorecard belongs to
  how the mask was drawn and never to what was done with the mask afterwards.
  It also says whether a mask reaches the edge of its picture, because the
  footprint fitted to a glass the frame cut in half is part of a footprint and a
  solution refusing on width needs to know which it has. The observation is the
  bench's; what to do about it is each solution's.
- `marking.py` — the survey itself: it asks a solution about each station's
  picture, decides which station to believe where two overlap, and writes the
  answer down in one vocabulary. Each solution's own `run.py` calls it. It is
  not called `run.py` because every solution's runner is, and the two would
  shadow each other.
- `scoring.py` — the scorecard. It judges which real glass each report is, how
  far the place sat from the truth, and how well the mask was drawn: how much of
  the real glass it covered and how much of it was not that glass, broken down
  by kind of glass.
- `floor.py` — the best answer any method here could give. It runs the
  renderer's own masks through the same arithmetic and the same marking, so
  every result in this folder can be read against what is actually achievable.
- `device.py` — which processor the work runs on.

## This bench's camera is simpler than the cell's, on purpose

Worth knowing before any number here is set beside a number from the cell. The
cell's wrist camera is an **Intel RealSense D405**: it sees 87 degrees across
and is read at 640 by 360 pixels. This bench draws its pictures through a
simpler lens — 60 degrees across at 320 by 240 — and keeps its own margin for
how much of a picture's edge to give up, rather than reading the cell's
gripper.

There are two reasons, and the second is the important one.

The first is simply that every result in this problem was measured through this
lens, and through stations placed with that margin. Changing either changes
every picture, so it would change every mask, every width and every score
already committed, and nothing would be comparable with anything.

The second is that **none of it changes the question this problem asks.** The
question is how well six methods find glasses in a picture, and the
[comparability contract](../../docs/02-segment-glasses/the-examiner.md) gives all
six the *same* picture. So the lens cancels out of the comparison: a wider one
would make every method's job harder in the same way, and the ranking is what
this problem is for. Problem 2 and the cell therefore do not have to agree
about the camera, and this problem is better off holding still.

What would be wrong is letting a reader assume this is the cell's camera. It is
a stand-in chosen to keep the explanation simple. Where a number here is
compared with one from the cell, the document says which camera it came from,
and the real one is described in [the cell](../../docs/the-cell.md).