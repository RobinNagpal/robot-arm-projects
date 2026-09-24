# Problem 2 — the two approaches compared

Two ways of doing the same job, tested on the same 50 scenes (250 glasses):

- [`problem-2-learned`](../problem-2-learned/) — three small models, each
  trained on 200 pictures.
- [`problem-2-programmed`](../problem-2-programmed/) — geometry and written
  rules only, with no training.

Both use the scenes, pictures and scorecard in
[`problem-2-sim`](../problem-2-sim/). Neither was trained or tuned on these
50 scenes. The numbers come from each folder's `results.json`.

## The results

| Step | What is measured | Learned | Programmed |
|---|---|---|---|
| **1. Find** | glasses found, of 250 | 250 | 250 |
| | missed / merged / split / false | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| | position error, median · worst | 0.4 · 1.3 mm | 0.2 · 1.2 mm |
| **2. Choose a view** | first choice unspoiled | 232 of 245 (95%) | **246 of 250 (98%)** |
| | a random allowed place, for scale | 219 of 245 (89%) | 223 of 250 (89%) |
| | handed to problem 3 | 5 | **2** |
| **3. Measure** | glasses measured | 245 | 248 |
| | height error, median · worst | 5.4 · 36 mm | **0.8 · 2.3 mm** |
| | width error, median | 2.4 mm | **1.7 mm** |

## What each number means

**Position error.** How far the found middle of a glass is from where it
really stands, flat on the table. The arm uses this to aim the camera and,
later, the fingers.

**Missed, merged, split, false.** *Missed*: a real glass not found. *Merged*:
two real glasses reported as one. This is the dangerous one, because it looks
like one large glass and nothing downstream questions it. *Split*: one glass
reported as two. *False*: a glass found where there is none.

**Unspoiled view.** A side picture is spoiled when another glass is in it
badly enough to change the measurement: part of the target is hidden, or a
neighbour joins its outline. The simulator checks this by taking the same
picture again with the target standing alone and comparing the two. "A
random allowed place" is the same check on a random place that passed the
veto. It shows how much the choosing adds over not choosing at all.

**Handed to problem 3.** Glasses the approach declined to measure, because no
place looked clean enough. That is a correct answer, not a failure: problem 3
moves glasses apart.

**Height error.** The measured height of the glass minus its true height.
+5 mm means it was measured 5 mm too tall. The table shows the median over all
measured glasses, sign ignored, and the single worst one. It matters because
the height decides where the glass is held and how far it is lowered onto the
rack.

**Width error.** How wide the glass is, compared at 16 heights spread evenly
from its foot to its rim. At each height: measured width minus true width,
sign ignored. The middle of those 16 is the glass's width error, and the table
shows the median over all glasses. It matters because the fingers open to the
width at the grip height.

## What the comparison says

**Finding is a tie.** With glasses 150 mm apart both are near perfect. This
is the easy case: they rarely overlap even in the picture. Crowded tables are
problem 3.

**Choosing: the written rule wins.** The rule measures the one thing that
spoils a view: the gap, in the picture, between the target and any glass that
would cover it or join its outline. The ranker has to learn that from 200
examples, of which only about 50 were spoiled. It beats random placement but
not the rule.

**Measuring: the programmed way wins clearly.** The camera looks level from
120 mm up. For a tall glass, the top of its outline is the near side of the
rim, which is closer to the camera than the glass's middle, so it reads tall.
That error comes from where the lens is, so it can be worked out and removed
exactly, which the programmed way does. The learned model has to pick it up
from examples. It gets the typical glass roughly right, but reads the tallest
stemmed glasses 15–36 mm short, because 200 examples cover the tallest ones
thinly.

**The general lesson.** Where the answer can be worked out exactly, as here
with a known camera, known distances and opaque glasses, working it out beats
learning it. Learning pays when the rule cannot be written: real glass that
is see-through, shiny or wet, and depth readings that go wrong. None of that
happens in this simulator.

## What these results do not cover

- **Not Gazebo.** The pictures come from `problem-2-sim/render.py`, which uses
  the wrist camera's lens but not the simulator. The arm never moves, and no
  inverse kinematics or motion planning is checked.
- **Opaque, clean depth.** No noise, no reflections, no transparency, which
  flatters the programmed way.
- **One learned run.** The learned models were trained once, on 200 pictures,
  before a renderer fix for glasses very near the camera. They were scored
  after the fix without retraining. `make train` in `problem-2-learned` redoes
  it in about a minute.

## Reproducing

```
cd ../problem-2-programmed && make run
cd ../problem-2-learned && make train && make run
```
