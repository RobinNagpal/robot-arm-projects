# Problem 2 — SAM 2 with a keeper

A borrowed model, SAM 2, is prompted with a grid of points and outlines
everything in the picture. A small model fitted here, the **keeper**, looks at
each outline and says whether it is one glass. Nothing that finds objects is
fitted here.

[`docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md`](../../docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md)
explains the solution and is its specification. This file says how to run it
and what it produced.

## The two rungs

The document calls these the two ways. Both are here. The table shows, for each
rung, the model, its prompt, what decides "this is a glass", and what is fitted.

| rung | model | prompted with | what decides "this is a glass" | fitted here |
| --- | --- | --- | --- | --- |
| lower | SAM 2, `facebook/sam2.1-hiera-base-plus` | a grid of points | the keeper, in this folder | the keeper, in seconds |
| upper | SAM 3, `facebook/sam3` | the word "drinking glass" | the borrowed weights | nothing at all |

**The upper rung has not been run on this machine.** `transformers` here has
the model, and `sam3_words.py` follows its documented interface. But the
weights are gated and need an account with access, so there is no scorecard. SAM
2 is Apache 2.0 and downloads without an account. SAM 3 has its own terms; see
[the second way](../../docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md#the-second-way--a-word-instead-of-a-grid).

## The files

- `sam_keeper.py` — the lower rung: the grid of prompts, the cleanup, the eight
  measurements, the keeper and its two thresholds.
- `sam3_words.py` — the upper rung: one word, no grid, no keeper.
- `reports.py` — the end of both rungs: the width check against the kind, and
  one report per place on the table. A report the frame cut short is not put to
  the width check. Nothing in it is fitted.
- `weights.py` — fetches the borrowed weights into `weights/`, which is not
  committed.
- `train.py` — fits the keeper. Its table is the only place that tells the two
  rungs apart.
- `run.py` — scores a rung on the held-out scenes and writes its `results-*.json`.
- `show_keeper.py` — prints the keeper's inputs beside its answer.
- `test_keeper.py` — the checks that need no weights and no network.

The scenes, the camera, the shading and the scorecard are in
[`../bench`](../bench/). Every solution in this problem shares them, so a
difference in a scorecard belongs to the masks.

## Running it

```
make fetch                  # the borrowed weights, 320 MB, once
make train                  # fit the keeper: SAM 2 over 12 scenes, then seconds of trees
make run                    # score it on 20 held-out spawned scenes
make crowded                # the same, where one glass really does hide another
make show                   # the keeper's eight measurements beside its answer
make test                   # the quick checks
```

Every target takes `RUNG=sam3` for the upper rung, and `SCENES=n`.

## What it explains

`make show` prints each proposal in one real picture. For each, it shows the
eight measurements the keeper got and its three calibrated chances. Then it
shows what the arithmetic after it did, and what the proposal really was:

```
seed 10000, station 1 of 3, straight_glass, 5 on the table, 6 proposals

proposal 1: 63070 pixels at (0.434, -0.347) m, 585 mm wide
          12.002  how wide the circle fitted to it is, against the range this kind allows
           0.357  how round it is: its area against the area its outline could enclose
           0.000  how far its surface stands above the table, from the depth reading
           0.047  how far it sits from the point directly below the camera
         813.000  how many prompt points returned this same mask
           0.245  how much of its outline is a step in depth rather than a smooth run
      165557.845  its area on the table, in square millimetres
           0.000  whether another proposal contains it, or it contains one
              ->  not a glass, from not a glass 0.73, one glass 0.16, more than one glass 0.11
              so  dropped
       the truth  not a glass

proposal 2: 4270 pixels at (0.574, -0.396) m, 67 mm wide
           0.484  how wide the circle fitted to it is, against the range this kind allows
           0.886  how round it is: its area against the area its outline could enclose
           0.164  how far its surface stands above the table, from the depth reading
           0.103  how far it sits from the point directly below the camera
          59.000  how many prompt points returned this same mask
           1.000  how much of its outline is a step in depth rather than a smooth run
        3708.171  its area on the table, in square millimetres
           0.000  whether another proposal contains it, or it contains one
              ->  keep, from not a glass 0.01, one glass 0.85, more than one glass 0.14
              so  reported as a glass
       the truth  one glass
```

The first proposal is the table. It is twelve of these glasses wide, it lies at
the table's own height, and 813 grid points agreed on it. All eight numbers say
so, and a person can check that. The upper rung has nothing like this to print.

## What it costs

Each picture costs one pass of SAM 2's picture encoder and about 970 cheap
prompts. That took about eight seconds a picture on this machine's GPU through
MPS: 36 pictures in 273 s for the training run. A survey is three pictures, so a
scene costs about half a minute. Fitting the keeper takes under a second of
processor time; a training run spends its time on SAM 2. No separate graphics
card and no CUDA are involved, and the borrowed weights are never trained.

## Results

`run.py` scores the solution on arrangements no training has seen. One run
scores 20 of them, which is too few to trust one run. So the solution was run
over **five blocks of 20 arrangements each**, seeds 10000 to 10099. The table
below combines the five. The keeper was fitted once, on 12 training scenes (36
pictures, 208 proposals, calibrated with a fitted sigmoid over three folds).
Every block used those same weights. So the spread shows which arrangements were
drawn, not which training run was got.

Counts are per 100 glasses, because the blocks hold slightly different numbers
of glasses. Medians cannot be averaged honestly, so a median row is the mean of
the five blocks' medians. A worst row is the worst any block saw. Read each row
as the average, with the range across blocks in brackets. The upper rung has no
column, because it could not be run.

| five blocks, 100 arrangements, per 100 glasses | spawned | crowded |
| --- | --- | --- |
| glasses on the table | 499 | 485 |
| found | 83.0 (78.0–86.1) | 73.6 (71.9–76.6) |
| missed | 17.0 | 26.4 |
| merged / split / false | 0.0 / 0.2 / 0.0 | 0.0 / 0.0 / 0.0 |
| position error, mean of block medians · worst block | 5.6 · 47.6 mm | 0.8 · 37.3 mm |
| mask covered, mean of block medians · worst block | 97.2% · 42.7% | 98.3% · 63.7% |
| mask not the glass, mean of block medians · worst block | 0.0% · 1.1% | 0.0% · 14.9% |
| handed over, cannot tell | 127.1 | 108.9 |
| handed over, width the kind cannot have, whole of it in frame | 0.8 | 1.6 |
| handed over, a pair that did not come apart | 0.0 | 0.4 |

Almost nothing wrong is reported. No glass is invented or merged, and one glass
in all 499 spawned sightings was split in two. What it cannot settle, it hands
over, which is what this project asks. Most handovers are proposals in the band
between the keeper's two thresholds. There are more of those than glasses: 127
per 100 glasses on the spawned scenes, against 17 missed. The keeper was fitted
on only 208 rows. More rows is the one lever this solution has on them:
`make train SCENES=40`, at about eight seconds a picture.

`bench/average_blocks.py` prints this table from the block files. The later
blocks were run with `--from-seed 10020` and the like.

The [results table](../results/README.md) sets these numbers beside the other
five solutions.

### What not refusing on a cut-off region was worth

`reports.legal` used to put every report to the width check. Now it reads
`masks_to_glasses.Found.cut_off` first. The table compares the two versions:
same keeper, same weights, same scenes. These are counts from one block of 20
arrangements, not five-block averages, because one block shows the difference
most clearly when nothing else changes. In each cell, the number before the dot
is before the change and the number after it is after.

| one block of 20 arrangements | spawned: before · after | crowded: before · after |
| --- | --- | --- |
| **found, of the glasses put out** | 76 · **81** of 100 | 71 · **73** of 101 |
| missed | 24 · **19** | 30 · **28** |
| merged / split / false | 0 / 0 / 0 · 0 / 0 / 0 | 0 / 0 / 0 · 0 / 0 / 0 |
| position error, median | 2.6 · 3.0 mm | 0.9 · 1.0 mm |
| handed over, width the kind cannot have | 18 · **0** | 11 · **1** |
| handed over, a pair that did not come apart | 0 · 0 | 1 · **0** |

**All 18 width refusals on the spawned scenes were regions the frame had cut
short**, since none is left. On the crowded scenes, 10 of the 11 were. Seven
glasses came back. They cost 0.4 mm of median place on the spawned scenes and
0.1 mm on the crowded ones. Nothing wrong was reported: no glass invented,
merged or split. The one crowded pair that would not come apart now does. The
second round of prompts puts both halves to the width check, and the check no
longer refuses a half the frame cut short.

`reports.py` holds the measurement behind this change. Handed the bench's exact
masks over 20 held-out spawned scenes, the kind's range refuses 66 of 297 glass
sightings. Every one of those 66 reaches the frame edge. [The
document](../../docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md#the-arithmetic-still-decides)
gives the argument.
