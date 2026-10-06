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
  pictures of them from any camera pose, drawn with the wrist camera's lens. It
  stands in for Gazebo. Scenes from one number upwards are for testing only, and
  no training may draw from them.
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
