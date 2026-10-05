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
- `reports.py` — what both rungs end with: the width check against the kind and
  one report per place on the table. Nothing in it is fitted.
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

`results-sam2.json` and `results-sam2-crowded.json` were written by `run.py` on
this machine, on 20 held-out scenes each, with the keeper fitted on 12 training
scenes (36 pictures, 208 proposals, calibrated with a fitted sigmoid over three
folds). The upper rung has no row here because it could not be run.

| on 20 held-out scenes | spawned | crowded |
| --- | --- | --- |
| glasses on the table | 100 | 101 |
| found | 76 | 71 |
| missed | 24 | 30 |
| merged / split / false | 0 / 0 / 0 | 0 / 0 / 0 |
| position error, median · worst | 2.6 · 43.1 mm | 0.9 · 28.7 mm |
| handed over, cannot tell | 120 | 108 |
| handed over, width the kind cannot have | 18 | 11 |
| handed over, a pair that did not come apart | 0 | 1 |

Nothing wrong is reported: no glass is invented, none is merged with another
and none is split in two. What it misses, it misses, and what it cannot settle
it hands over — which is the shape this project asks a doubtful answer to take.
Most of what it hands over is proposals that fell in the band between the
keeper's two thresholds — 120 of them on the spawned scenes against 24 glasses
missed. The keeper behind those answers was fitted on 208 rows, and more rows
is the one lever this solution has on them: `make train SCENES=40`, at about
eight seconds a picture.
