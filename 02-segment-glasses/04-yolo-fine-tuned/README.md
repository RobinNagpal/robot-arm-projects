# Solution 4 — the same model, fine-tuned here

This is Ultralytics YOLO26-seg at the small end of the family. It is **the same
file [solution 3](../03-yolo-zero-shot/) downloads**. Its training continues on
this cell's own pictures, and its list of everyday names becomes one class,
"glass". Its outlines are the masks. The bench's shared arithmetic turns each
mask into a place and a width. The reasoning is in
[`docs/solutions/04-yolo-fine-tuned.md`](../docs/solutions/04-yolo-fine-tuned.md).
The bench is described in
[`docs/the-examiner.md`](../docs/the-examiner.md).

## It is one half of a matched pair

Solution 3 is this model untrained. Everything else is held still, so the gap
between the two scorecards measures what fine-tuning bought. Three things must
stay true for that, and each is checked:

- **The same starting file.** `yolo_fine_tuned.MODEL` is `yolo26n-seg.pt`, and
  so is `yolo_zero_shot.MODEL`. These two constants must agree. If either
  moves, the pair compares two models instead of one. A test here checks that
  the model is named in one place only.
- **The same two settings.** The bar on the confidence number is 0.25. The
  overlap allowed before a candidate is dropped is 0.7. Both are solution 3's
  values. The bar could now be chosen on the training half. **That was not
  done**, so that a moved bar is not mistaken for what training bought.
- **The same pictures.** Both take the survey from the stations `bench/data.py`
  works out, at the cell's own survey height, three per scene.

One thing differs besides the training. This solution refuses a candidate whose
footprint no glass of the kind could have, and reports a doubt. Solution 3 has
no such check. The refusal can only turn a glass into a doubt, so it cannot
flatter this side.

**The refusal is skipped when a mask reaches the edge of the picture.** The
check now reads `masks_to_glasses.Found.cut_off` first. The document's section
[the masks are what this contributes](../docs/solutions/04-yolo-fine-tuned.md#the-masks-are-what-this-contributes)
gives the two measurements behind this: 66 of 297 sightings refused, all at the
frame edge.

## The files

- `yolo_fine_tuned.py` — the model, the two settings, and the same
  `Finder` / `find(picture, kind)` / `load(save)` interface the other solutions
  answer, plus a real `fit` that continues the borrowed file's training.
- `dataset.py` — the step that writes the bench's scenes out in the shape
  Ultralytics reads a training set in: the pictures as image files, one text
  file per picture holding each glass's outline, and a small YAML naming the
  one class. The outlines come from the renderer's own id picture.
- `train.py` — draws the scenes, builds the set, fine-tunes, saves the weights.
- `run.py` — the held-out scenes, scored; writes `results.json`.
- `test_fine_tuned.py` — the quick checks. No weights, no training, no network.

## Running it

```
pixi run python 04-yolo-fine-tuned/train.py                      # a short run
pixi run python 04-yolo-fine-tuned/train.py --scenes 100 --epochs 60
pixi run python 04-yolo-fine-tuned/run.py --scenes 20
pixi run python 04-yolo-fine-tuned/run.py --scenes 20 --crowded
pixi run pytest -q 04-yolo-fine-tuned
```

`train.py`'s defaults are small on purpose. A run finishes in about a minute
and shows the machinery working. **They are not enough to fit this model.**
The default run took 52 seconds, and its model never scored a candidate above
0.02, so `run.py` found nothing. The head is rebuilt for one class, so it
starts from nothing and needs real training. The numbers below came from the
larger settings.

The borrowed weights fetch themselves into `weights/` on the first training
run. Neither that file nor the fine-tuned one is committed. Delete `weights/`
to start again. Training also writes `dataset/` and `runs/`, which are not
committed.

## What it costs

Labels cost nothing, because the renderer marks every pixel with its glass. On
real pictures, labelling would be the most expensive part. Training took 39
minutes on this machine's integrated graphics, through PyTorch's MPS backend.
The licence is the real cost: the AGPL covers both YOLO26-seg and
`weights/fine-tuned.pt`. The document's sections on [the training
set](../docs/solutions/04-yolo-fine-tuned.md#where-the-training-set-comes-from)
and [the licence](../docs/solutions/04-yolo-fine-tuned.md#the-licence)
explain both.

## Results

**What produced them.** One training run and two scoring runs, all on this
machine:

```
pixi run python 04-yolo-fine-tuned/train.py --scenes 100 --epochs 60
pixi run python 04-yolo-fine-tuned/run.py --scenes 20
pixi run python 04-yolo-fine-tuned/run.py --scenes 20 --crowded
```

The training run drew 100 scenes from below the bench's dividing line: 50
spawned and 50 crowded, three pictures each. 75 scenes went into the fit, which
is 225 pictures holding 1034 outlines. 25 were kept back for the run to check
itself on. Settings: starting weights `yolo26n-seg.pt`, pictures letterboxed to
320, batch 8, seed 0, Ultralytics' default augmentation, on the GPU through
MPS. **It took 39 minutes.** The run's own check on its 75 held-back pictures
reached a mask mAP50 of 0.995. That is not a score of this solution, because
those pictures are below the dividing line. It only shows the fit converged.

Both scoring runs use the bar at 0.25 and the overlap at 0.7. Each uses 20
held-out scenes from its family, three stations each. Read each row across the
two families.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **99** | **73** |
| missed | 1 | 28 |
| merged / split / false | 0 / 0 / 0 | 1 / 0 / 0 |
| position error, median · worst | 5.5 · 46.5 mm | 0.9 · 74.5 mm |
| mask covered, median · worst | 99.8% · 92.2% | 99.3% · 88.3% |
| mask not the glass, median · worst | 4.4% · 17.7% | 3.9% · 21.2% |
| doubted: width outside the kind, whole glass in frame | 16 | 47 |

### What not refusing on a cut-off mask was worth

The width check used to run on every candidate. Each cell below shows the same
weights, settings and scenes, before and after the check read `cut_off` first:

| | spawned: before · after | crowded: before · after |
|---|---|---|
| **found, of the glasses put out** | 92 · **99** of 100 | 66 · **73** of 101 |
| missed | 8 · **1** | 35 · **28** |
| merged | 0 · 0 | 1 · 1 |
| position error, median | 3.5 · 5.5 mm | 0.5 · 0.9 mm |
| doubted on width | 73 · 16 | 106 · 47 |

Seven glasses came back on each family, fourteen in all, and none was merged.
The place got worse by 2.0 mm at the median and 3.9 mm at the worst on spawned
layouts. On crowded ones it got worse by 0.4 mm and 32.2 mm. That is the
expected price. The glasses that came back were seen whole by no station, so
they are the worst-placed reports. Before the repair, the check hid them.

The 16 and 47 that remain are refusals with the whole glass in frame. That is
the check doing its job. Each is a mask of one real glass whose edge read too
wide, or one region over two glasses.

### What the pair measures

This is the number the pair exists to produce. One is trained here and one is
not. The table gives found per 100 glasses, averaged over the five blocks of
held-out arrangements. Read each row across the two solutions and the floor:

| found per 100 glasses | solution 3, untrained | solution 4, trained here | the examiner's floor |
|---|---|---|---|
| spawned | 6.4 | **99.4** | 100.0 |
| crowded | 2.1 | **72.0** | 86.4 |
| place, middle glass (spawned) | 23.7 mm | 6.6 mm | 6.8 mm |

**That gap is what fine-tuning bought.** Solution 3 does find things in these
pictures, but it calls them sports balls and frisbees, and its filter drops
them. With one class, no name can be dropped. The domain gap is closed because
the weights were trained on these very pictures.

Three points about the table:

**On crowded scenes the floor is 83, not 101.** Eighteen glasses are fully
hidden from every station, so no method can report them. This solution's 73 is
10 short of what was there to find, not 28.

**The spawned median just below the floor's is not better than perfect.** The
two medians cover different glasses: the floor reports all 100, and this
solution reports 99.

**The refusals are the coarse outline, not false objects.** Over eight held-out
spawned scenes, before the repair: 92 candidates kept, 11 refused as too
narrow, and 20 refused as too wide. **Every one of the 11 narrow ones touched
the frame edge.** All 20 wide ones mostly cover exactly one real glass. So the
model found no table and no empty space. The check catches a glass whose edge
read too wide, which training does not fix.

At run time the model takes 0.089 s a picture, measured over ten passes with the
model loaded. A whole 20-scene run is a few seconds of model time.

## What training did not fix

[What training closes, and what it cannot
touch](../docs/solutions/04-yolo-fine-tuned.md#what-training-closes-and-what-it-cannot-touch)
explains each of these.

- **The outline's edge is still approximate**, so the width carries an error.
- **The masks are still modal.** A partly hidden glass is reported smaller and
  in the wrong place. Training towards the whole silhouette is [solution
  6](../docs/solutions/06-rf-detr-fine-tuned.md)'s
  choice, and `fit` refuses `amodal=True` rather than pretend otherwise.
- **A fully hidden glass is still invisible.** The cure is in
  [looking again at what was hidden](../docs/hidden-glasses.md).
- **The weights are a narrow asset.** Change the camera, the shading or a
  kind's range, and the file goes out of date. No test of the code would notice.
