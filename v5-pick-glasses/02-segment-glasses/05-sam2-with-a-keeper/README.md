# Problem 2 — SAM 2 with a keeper

Nothing that finds objects is fitted here. A borrowed foundation model is
prompted with a plain grid of points and outlines everything the picture holds,
and a small model fitted in this cell — the **keeper** — is handed each outline
on its own and says whether it is one glass.

The solution is described in
[`docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md`](../../docs/02-segment-glasses/solutions/05-sam2-with-a-keeper.md).
That document is the specification; this file only says how to run it.

## The two rungs

The document describes one approach at two generations, and both are here.

| rung | model | prompted with | what decides "this is a glass" | fitted here |
| --- | --- | --- | --- | --- |
| lower | SAM 2, `facebook/sam2.1-hiera-base-plus` | a grid of points | the keeper, in this folder | the keeper, in seconds |
| upper | SAM 3, `facebook/sam3` | the word "drinking glass" | the borrowed weights | nothing at all |

**The upper rung has not been run on this machine.** `transformers` here has
the model, and `sam3_words.py` is written against its documented interface, but
the weights are gated: the upload will not hand them over without an account
that has been granted access, so there is no scorecard for it and none has been
invented. That is also the practical note the document makes — the permissive
licence of one generation is not inherited by the next. SAM 2 is Apache 2.0 and
downloads without an account; SAM 3's terms are its own.

## The files

- `sam_keeper.py` — the lower rung: the grid of prompts, the cleanup, the eight
  measurements, the keeper and its two thresholds.
- `sam3_words.py` — the upper rung: one word, no grid, no keeper.
- `reports.py` — what both rungs end with: the width check against the kind,
  which a report the frame cut short is not put to, and one report per place on
  the table. Nothing in it is fitted.
- `weights.py` — fetches the borrowed weights into `weights/`, which is not
  committed.
- `train.py` — fits the keeper. The table in it is the only place that knows
  the two rungs apart.
- `run.py` — scores a rung on the held-out scenes and writes its `results-*.json`.
- `show_keeper.py` — prints the keeper's inputs beside its answer.
- `test_keeper.py` — the checks that need no weights and no network.

The scenes, the camera, the shading and the scorecard are
[`../bench`](../bench/), shared with every solution in this problem, so a
difference in a scorecard belongs to the masks and not to what was done with
them.

## Running it

```
make fetch                  # the borrowed weights, 320 MB, once
make train                  # fit the keeper: SAM 2 over 12 scenes, then seconds of trees
make run                    # score it on 20 held-out spawned scenes
make crowded                # the same, where one glass really does hide another
make show                   # the keeper's eight measurements beside its answer
make test                   # the quick checks
```

Everything takes `RUNG=sam3` to ask for the upper rung instead, and `SCENES=n`.

## What it explains

This is the one solution in the set where the deciding can be read. `make show`
prints, for every proposal in one real picture, the eight measurements the
keeper was given, the three calibrated chances it answered with, what the
arithmetic after it then did, and what the simulator says the proposal really
was:

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

The first of those two is the table: as wide as twelve of these glasses, lying
at the table's own height, and agreed on by 813 of the grid's points. Every one
of the eight numbers says so, and that is the argument a person can check.

The upper rung has nothing of the kind to print, which is the whole of what the
document weighs the two against each other over.

## What it costs

One pass of SAM 2's picture encoder per picture, and about 970 cheap prompts
after it, which measured about eight seconds a picture on this machine's GPU
through MPS: 36 pictures in 273 s for the training run. A survey is three
pictures, so a scene costs about half a minute. Fitting the keeper itself is
under a second of processor time; what a training run spends is SAM 2 over the
training scenes. No separate graphics card and no CUDA are involved, and the
borrowed weights are never trained.

## Results

`run.py` scores the solution on arrangements no training has seen. One run
scores 20 of them, which is a small enough sample that a score read off a single
run carries a sampling wobble the file itself cannot show. So the solution was
run over **five blocks of 20 arrangements each**, seeds 10000 to 10099 in blocks
of 20, and the table below is those five blocks together. The keeper was fitted
once, on 12 training scenes (36 pictures, 208 proposals, calibrated with a
fitted sigmoid over three folds), and every block was scored with those same
weights. So the spread in the table is "which arrangements did we draw" and not
"which training run did we get".

Counts are given per 100 glasses, because the blocks hold slightly different
numbers of glasses. A median cannot be averaged honestly, so the median rows are
the mean of the five blocks' own medians, and the worst rows are the worst any
block saw. Read a row as the average first and the range in brackets as how far
the blocks moved around it. The upper rung has no column here because it could
not be run.

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

Almost nothing wrong is reported: no glass is invented and none is merged with
another, and one glass in all 499 spaced sightings was split in two. What it
misses, it misses, and what it cannot settle it hands over — which is the shape
this project asks a doubtful answer to take. Most of what it hands over is
proposals that fell in the band between the keeper's two thresholds, and there
are more of those than there are glasses: 127 per 100 glasses on the spawned
scenes against 17 glasses missed. The keeper behind those answers was fitted on
208 rows, and more rows is the one lever this solution has on them:
`make train SCENES=40`, at about eight seconds a picture.

`bench/average_blocks.py` prints this table from the block files, and
`--from-seed 10020` and its fellows are how the later blocks were run.

### What not refusing on a cut-off region was worth

`reports.legal` used to put every report to the width check. The two columns
below are the same keeper, the same weights and the same scenes, with the only
difference being that the later version reads `masks_to_glasses.Found.cut_off`
first. These are counts from one block of 20 arrangements rather than the
five-block averages above, because the point here is the difference between two
versions on identical scenes, and that difference is clearest when nothing else
changes:

| one block of 20 arrangements | spawned: before · after | crowded: before · after |
| --- | --- | --- |
| **found, of the glasses put out** | 76 · **81** of 100 | 71 · **73** of 101 |
| missed | 24 · **19** | 30 · **28** |
| merged / split / false | 0 / 0 / 0 · 0 / 0 / 0 | 0 / 0 / 0 · 0 / 0 / 0 |
| position error, median | 2.6 · 3.0 mm | 0.9 · 1.0 mm |
| handed over, width the kind cannot have | 18 · **0** | 11 · **1** |
| handed over, a pair that did not come apart | 0 · 0 | 1 · **0** |

**Every one of the 18 width refusals on the spawned scenes was a region the
frame had cut short**, since none of them is left, and 10 of the 11 on the
crowded scenes were. Seven glasses came back for 0.4 mm of median place on the
spawned scenes and 0.1 mm on the crowded ones, and nothing wrong was reported
for any of them: still no glass invented, merged or split. The one crowded pair
that used to be handed over because it would not come apart now does come apart,
because the second round of prompting inside it puts both halves to the same
check and the check no longer refuses a half the frame cut short.

Why the refusal was worth repairing is in `reports.py`, with the measurement:
handed the bench's own exact masks, one station at a time over 20 held-out
spawned scenes, the kind's range of footprints refuses 66 of 297 glass
sightings, and every one of those 66 reaches the frame edge. The check was
refusing the view and not the region.
