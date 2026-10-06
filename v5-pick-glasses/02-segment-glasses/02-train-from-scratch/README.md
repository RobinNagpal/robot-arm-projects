# Solution 2 — a network trained here from scratch

A small U-Net written in this project and fitted from random numbers on the
bench's own arrangements. At every pixel it calls glass it predicts a short
arrow pointing at the middle of that pixel's own glass; adding the arrow to the
pixel's place is a vote, the votes pile up, and one pile is one glass. **Nothing
is borrowed**: no downloaded weights, no pre-trained backbone, no licence
condition. Its document is
[`docs/02-segment-glasses/solutions/02-train-from-scratch.md`](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md),
and the bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

## The files

- `models.py` — TopNet, which is the solution. Also the Ranker and SideNet; see
  below.
- `pipeline.py` — the votes, the piles, the masks, and the same
  `Finder.find(picture, kind)` interface the other five solutions answer. It
  hands back a boolean mask per glass; the place and the width come from the
  bench's `masks_to_glasses`.
- `train.py` — draws the bench's training arrangements and fits the models.
  TopNet trains on every station of every training scene, half of them crowded,
  with the simulator's own record of which glass each pixel shows as the labels.
- `run.py` — the held-out scenes over the survey's three stations, scored;
  writes `results.json` and `results-crowded.json`.
- `show_top_net.py`, `drawing.py` — pictures of what TopNet is taught and what
  it answers. See [looking at the data](#looking-at-the-data).
- `test_learned.py` — the quick checks. No trained weights needed.
- `viewpoints.py`, the `Ranker` and `SideNet` in `models.py`,
  `pipeline.rank_views`, `pipeline.measure`, `show_ranker.py`,
  `show_side_net.py` — **not part of this problem.** The bench stops at a mask,
  a place and a width; choosing a viewpoint and reading a glass's profile from
  the side are the steps after that, and nothing in `run.py` touches them. They
  are kept because
  [problem 4's documents](../../docs/problem-4/solutions/learned/08-the-learned-pipelines-retrained.md)
  name this folder's Ranker and SideNet as parts their pipeline reuses.

## How the finding works

```
one station's picture ──TopNet──▶ per pixel: glass or not, and the way to the
                                  middle of its own glass
the votes             ──tally──▶  one pile per glass
the pixels of a pile  ──the bench──▶ a place on the table and a width
```

| | |
|---|---|
| kind | small U-Net, 144 thousand weights |
| given | 3 grids of 160 × 120: height above the table, row, column |
| gives back | 3 grids: glass or not, and the two parts of the arrow |
| trained on | 600 pictures — 200 arrangements × 3 stations, half of them crowded |
| labels | the simulator's record of which glass each pixel shows (rung one) |

The height channel is worked out from the picture's own camera pose rather than
from a height written down, because the cell surveys from three stations and a
fixed height would be nonsense at the other two.

**Where in the frame each pixel sits is handed in as two more channels**, and it
is the one fact a pixel cannot see: a camera looking straight down throws a
glass's outline outwards from the point below the lens, further the taller the
glass, so the direction to a glass's middle depends on where in the frame the
pixel is.

## Running it

```
pixi run python 02-train-from-scratch/train.py --scenes 200
pixi run python 02-train-from-scratch/run.py --scenes 20
pixi run python 02-train-from-scratch/run.py --scenes 20 --crowded
pixi run pytest -q 02-train-from-scratch
```

The weights are not committed, so train before running. Nothing downloads.

## What it costs

Training all three models on 200 arrangements takes about ten minutes on this
machine's integrated graphics through the MPS backend, nearly all of it TopNet's
600 pictures. A 20-scene run over three stations each — 60 pictures — takes
about 20 seconds including the rendering. No labelling by hand, because the
simulator knows which glass each pixel shows, and no graphics card of its own.

## Results — 20 held-out scenes from each family, three stations each

Trained on 200 arrangements, which is 600 survey pictures, half of them crowded.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **63** | **72** |
| missed | 37 | 29 |
| merged / split / false | 0 / 0 / 0 | 1 / 0 / 0 |
| position error, median · worst | 0.5 · 19.1 mm | 0.7 · 43.8 mm |
| mask covered, median · worst | 98.2% · 92.7% | 97.2% · 80.3% |
| mask not the glass, median · worst | 1.5% · 4.1% | 1.4% · 17.5% |

**Of the glasses it reports, it is as close to the floor as a method can get.**
The bench's floor — the same arithmetic on the masks the renderer itself drew —
is 6.3 mm median on spawned layouts and 0.4 mm on crowded ones. 0.5 mm and
0.7 mm are at that limit, so there is nothing left in the places to win.

**The masks are even across the four kinds, which is the result worth having.**

| kind | covered | not the glass |
|---|---|---|
| straight glass | 98.0% | 1.8% |
| tapered glass | 98.5% | 1.9% |
| stemmed glass | 98.6% | 1.3% |
| short stemmed glass | 96.8% | 1.5% |

That is the comparison
[the examiner document](../../docs/02-segment-glasses/the-examiner.md) predicts, and
it comes out as predicted: a fitted model covers all four kinds almost equally
well, the stemmed glass included, where `01-rules-on-the-table` covers the two
stemmed kinds 11–13 points worse than the two without a stem. And it pays for
that in the other number, in the opposite direction: 1.5% of every mask here is
not the glass, where the written rule's masks are at 0.0%, because a learned
outline follows the shape coarsely and its edge sits a little outside the glass.
Neither habit can be seen in the places.

**What it misses, it cannot see at all.** 37 of 100 glasses are missed on
spawned layouts, and that is not the network. A vote is a place in the picture
and the tally is the size of the picture, so a glass whose own middle falls
outside the frame votes nowhere. Of the 100 glasses put out, only **61** have
their rim's middle inside any of the three stations' pictures, and 63 were
found; on crowded layouts the counts are 84 and 72. So the design is already
within a few glasses of its own ceiling, and the ceiling — not the training — is
what the missed column measures. The repair is a tally with a margin round the
picture, not a better network.

### What the training set was worth

The weights before this change were fitted on one picture per scene from
`render.top_pose`, 750 mm above the zone, which is not what the bench hands a
solution. Scored on the bench's survey pictures they give:

Both rows below are a single run over the first block of 20 held-out
arrangements, because the older weights were never re-run over the five blocks
the results page averages. They are comparable with each other and not with the
averaged numbers there.

| | found of 100 | place, middle glass | mask covered |
|---|---|---|---|
| fitted on the 750 mm top view | 100 | 17.3 mm | 84.3% |
| fitted on the examiner's stations | 63 | 0.5 mm | 98.2% |

The first row looks better and is worse, which is worth understanding. The old
weights learned their arrows on a view where a rim leans barely at all, so on
these pictures they predict arrows that are far too short. A short arrow for a
glass near the frame edge lands *inside* the picture instead of outside it, so a
pile forms and the glass is counted — at a middle that is wrong, which is where
the 17.3 mm and the 84.3% come from. **It found more glasses by being wrong
about where their middles are.** Reading the found column on its own would have
rewarded exactly that.

## What this does not do

- **No width check, and the document asks for one.** The document prescribes
  fitting a circle to the pixels of a pile and refusing a pile whose width falls
  outside the range this kind of glass can be. It is not built. A refusal was
  tried and measured, and it is worse than nothing: the bench's own exact masks,
  judged one station at a time, give a footprint outside the kind's range for 66
  of 297 glass sightings, because a glass clipped at the edge of one station's
  frame shows only part of its footprint. The station that saw a glass squarely
  is chosen by the bench afterwards, where a solution has no say, so the check
  belongs after the survey rather than inside one picture.
- **No rung two.** The document's second rung takes its labels from the arm's
  own movement rather than from the answer key. It is a design and is not built;
  `train.py` fits rung one.
- **No domain randomisation.** The document asks for the lighting, the table's
  shade, the glass tint, the exposure and the noise to be varied so that shape
  is the only thing left that predicts the answer. The bench renders one table
  under one setting, so nothing here is varied and the network is free to use
  the renderer's constants as a clue. It would not survive a changed light, and
  no number in this folder would show it.
- **A glass whose middle is off the picture cannot be voted for.** A vote is a
  place in the picture and the tally is the size of the picture, so a glass whose
  own middle falls outside the frame votes nowhere. The survey does not rescue
  it: the stations are spread along one axis only, because one picture already
  covers the glass zone across the other, and a glass at the far edge of that
  other axis has its rim thrown outside the frame from every station. The repair
  is a tally with a margin round the picture, not a better network.
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.

## Looking at the data

`make show` saves pictures of what each model is taught and what it answers,
into `saved/`. It trains nothing; it uses the weights in `weights/`.

```
pixi run python 02-train-from-scratch/show_top_net.py train --scenes 10
pixi run python 02-train-from-scratch/show_top_net.py test --scenes 10
pixi run python 02-train-from-scratch/show_top_net.py test --scenes 10 --crowded
```

Each scene gets a `.png` to look at, a `.npz` holding every number behind it,
and a `.json` with four pixels written out in full: three on glass and one off
it, ringed in red in the first panel. One station of the three is drawn, the
middle one, which is the station the crowded family's lines of glasses run out
from.

**`train/` — four panels each.** The height of each pixel above the table;
whether each pixel is glass; and the way from each pixel to the middle of its
glass's rim, drawn once as a colour and once as arrows.

**`test/` — six panels each.** What TopNet is given and the two things it says
back; then where the arrows land and which middles were picked, the glasses made
from them with the true middles marked, and how far each arrow is from the true
one. Under the panels, each found glass's place and width beside the true ones.
In the `.json`, `glass_score` is TopNet's raw answer (above 0 means glass) and
`glass_chance` is the same answer as a chance between 0 and 1.

A `.npz` holds number grids and has to be opened with Python:

```
pixi run python -c "
import numpy as np
d = np.load('02-train-from-scratch/saved/top-net/train/scene-00002.npz')
for k in d.files: print(k, d[k].shape)
print(d['target'][:, 31, 38])     # the 3 true answers for the pixel at row 31, column 38
"
```

`show_ranker.py` and `show_side_net.py` do the same for the two models that are
not part of this problem; their panels are described in
[problem 4's document](../../docs/problem-4/solutions/learned/08-the-learned-pipelines-retrained.md).
