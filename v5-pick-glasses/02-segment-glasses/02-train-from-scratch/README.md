# Solution 2 — a network trained here from scratch

A small U-Net, written here and trained from random numbers on the bench's
arrangements. Each glass pixel votes for the middle of its own glass, and one
pile of votes is one glass. **Nothing is borrowed**: no downloaded weights and
no licence condition. The reasoning is in
[`docs/02-segment-glasses/solutions/02-train-from-scratch.md`](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md).
The bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

## The files

- `models.py` — TopNet, which is the solution. Also the Ranker and SideNet; see
  below.
- `pipeline.py` — the votes, the piles and the masks, behind the same
  `Finder.find(picture, kind)` interface as the other five solutions. It
  returns one boolean mask per glass. The bench's `masks_to_glasses` turns
  each mask into a place and a width.
- `train.py` — draws the bench's training arrangements and fits the models.
  TopNet trains on every station of every training scene, half of them crowded.
  Its labels are the simulator's record of which glass each pixel shows.
- `run.py` — scores the held-out scenes over the survey's three stations.
  Writes `results.json` and `results-crowded.json`.
- `show_top_net.py`, `drawing.py` — pictures of what TopNet is taught and what
  it answers. See [looking at the data](#looking-at-the-data).
- `test_learned.py` — the quick checks. No trained weights needed.
- `viewpoints.py`, the `Ranker` and `SideNet` in `models.py`,
  `pipeline.rank_views`, `pipeline.measure`, `show_ranker.py`,
  `show_side_net.py` — **not part of this problem.** The bench stops at a mask,
  a place and a width. Choosing a viewpoint and reading a profile from the side
  come later, and `run.py` does not touch them. They stay because
  [problem 5's documents](../../docs/problem-5/solutions/learned/08-the-learned-pipelines-retrained.md)
  reuse this folder's Ranker and SideNet.

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

"Rung one" is the document's [first
way](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md#the-first-way--labels-from-the-answer-key).
The height channel comes from each picture's own camera pose. A fixed height
would be wrong, because the cell surveys from three stations. The row and
column channels are explained in [what goes
in](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md#what-goes-in).

## Running it

```
pixi run python 02-train-from-scratch/train.py --scenes 200
pixi run python 02-train-from-scratch/run.py --scenes 20
pixi run python 02-train-from-scratch/run.py --scenes 20 --crowded
pixi run pytest -q 02-train-from-scratch
```

The weights are not committed, so train before running. Nothing downloads.

## What it costs

Training all three models on 200 arrangements takes about ten minutes. It runs
on this machine's integrated graphics through the MPS backend. Nearly all the
time is TopNet's 600 pictures. A 20-scene run over three stations each (60
pictures) takes about 20 seconds, rendering included. Nothing is labelled by
hand, and no graphics card is needed.

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

**For the glasses it reports, it is at the floor.** The bench's floor is the
same arithmetic run on the renderer's own masks. It is 6.3 mm median on spawned
layouts and 0.4 mm on crowded ones. 0.5 mm and 0.7 mm are at that limit, so the
places cannot get better.

**The masks are even across the four kinds.** This is the result worth having.

| kind | covered | not the glass |
|---|---|---|
| straight glass | 98.0% | 1.8% |
| tapered glass | 98.5% | 1.9% |
| stemmed glass | 98.6% | 1.3% |
| short stemmed glass | 96.8% | 1.5% |

[The examiner document](../../docs/02-segment-glasses/the-examiner.md)
predicted this. A trained model covers all four kinds almost equally, stemmed
glasses included. `01-rules-on-the-table` covers the two stemmed kinds 11–13
points worse than the two without a stem. The price is in the other number:
1.5% of each mask here is not the glass, against 0.0% for the written rule. A
learned outline is coarse, and its edge sits a little outside the glass.
Neither habit shows in the places.

**What it misses, it cannot see at all.** It misses 37 of 100 glasses on
spawned layouts, and the network is not the cause. A vote is a place in the
picture, and the tally is the size of the picture. So a glass whose middle is
outside the frame votes nowhere. Of the 100 glasses put out, only **61** have
their rim's middle inside any station's picture, and 63 were found. On crowded
layouts the counts are 84 and 72. So the design is near its own ceiling. The
missed column measures that ceiling, not the training. The repair is a tally
with a margin round the picture, not a better network.

### What the training set was worth

The earlier weights were fitted on one picture per scene from
`render.top_pose`, 750 mm above the zone. The bench does not hand a solution
that view. The table below scores them on the bench's survey pictures.

Both rows are one run over the first block of 20 held-out arrangements. The
older weights were never re-run over the five blocks the results page
averages. So compare the two rows with each other, not with that page.

| | found of 100 | place, middle glass | mask covered |
|---|---|---|---|
| fitted on the 750 mm top view | 100 | 17.3 mm | 84.3% |
| fitted on the examiner's stations | 63 | 0.5 mm | 98.2% |

The first row looks better but is worse. The old weights learned their arrows
on a view where a rim barely leans. On these pictures their arrows are far too
short. A short arrow for a glass near the frame edge lands *inside* the
picture, not outside. So a pile forms and the glass is counted, at the wrong
middle. That gives the 17.3 mm and the 84.3%. **It found more glasses by being
wrong about their middles.** The found column alone would have rewarded that.

## What this does not do

- **No width check, though the document asks for one.** It is not built. A
  refusal was tried, and it is worse than nothing. The bench's own exact masks,
  judged one station at a time, give a footprint outside the kind's range for 66
  of 297 glass sightings. A glass clipped at a frame edge shows only part of its
  footprint. The bench picks the station that saw a glass squarely, after the
  solution answers. So the check belongs after the survey, not inside one
  picture.
- **No rung two.** The document's [second
  way](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md#the-second-way--labels-from-the-arms-own-movement)
  takes labels from the arm's movement. It is a design only; `train.py` fits
  rung one.
- **No [domain
  randomisation](../../docs/02-segment-glasses/solutions/02-train-from-scratch.md#the-training-set).**
  The bench renders one table under one setting. The network may use the
  renderer's constants as a clue. It would not survive a changed light, and no
  number in this folder would show it.
- **A glass whose middle is off the picture cannot be voted for**, as the
  results above show. The survey does not rescue it. The stations lie along one
  axis only, because one picture already covers the zone across the other. A
  glass at the far edge of that other axis has its rim thrown out of the frame
  from every station.
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

Each scene gets three files:

- a `.png` to look at;
- a `.npz` holding every number behind it;
- a `.json` with four pixels written out in full, three on glass and one off it.
  They are ringed in red in the first panel.

Only the middle station of the three is drawn. The crowded family's lines of
glasses run out from that station.

**`train/` — four panels each.** The height of each pixel above the table.
Whether each pixel is glass. The way from each pixel to its rim's middle, drawn
once as a colour and once as arrows.

**`test/` — six panels each.** What TopNet is given, and its two answers. Where
the arrows land and which middles were picked. The glasses made from them, with
the true middles marked. How far each arrow is from the true one. Under the
panels, each found glass's place and width beside the true ones. In the
`.json`, `glass_score` is TopNet's raw answer (above 0 means glass).
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

`show_ranker.py` and `show_side_net.py` do the same for the two models outside
this problem. Their panels are described in
[problem 5's document](../../docs/problem-5/solutions/learned/08-the-learned-pipelines-retrained.md).
