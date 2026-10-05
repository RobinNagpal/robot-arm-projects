# Solution 4 — the same model, fine-tuned here

Ultralytics YOLO26-seg at the small end of the family, **the same file
[solution 3](../03-yolo-zero-shot/) downloads**, with its training continued on
this cell's own pictures and the borrowed list of everyday categories replaced
by the single class "glass". The outlines it then returns are the masks, and
the bench's shared arithmetic turns each mask into a place and a width. Its
document is
[`docs/02-segment-glasses/solutions/04-yolo-fine-tuned.md`](../../docs/02-segment-glasses/solutions/04-yolo-fine-tuned.md),
and the bench it is scored on is
[`docs/02-segment-glasses/the-bench.md`](../../docs/02-segment-glasses/the-bench.md).

## It is one half of a matched pair

Solution 3 is this model untrained. Everything else is held still, so the gap
between the two scorecards is a measurement of what fine-tuning bought and of
nothing else. Three things have to stay true for that to hold, and all three
are checked rather than hoped for:

- **The same starting file.** `yolo_fine_tuned.MODEL` is `yolo26n-seg.pt`, and
  so is `yolo_zero_shot.MODEL`. They are two constants in two folders and they
  must agree; if either moves, the pair becomes a comparison of two models
  rather than of one model trained and untrained. A test here asserts the model
  is named in one place only, so there is one line to compare.
- **The same two settings.** The bar on the confidence number is 0.25 and the
  overlap allowed before a candidate is discarded is 0.7, which are solution
  3's values, unmoved. The document says the bar could now be chosen on the
  bench's training half, since the number comes from weights fitted here.
  **That was not done**, deliberately: a moved bar could be mistaken for what
  training bought.
- **The same pictures.** Both take the survey from the stations `bench/data.py`
  works out, at the cell's own survey height, three per scene.

One thing does differ besides the training, and it is worth naming. This
solution refuses a candidate whose footprint no glass of the kind could have,
and reports it as a doubt; solution 3 deliberately has no such check. That
refusal can only turn a reported glass into a reported doubt, never the other
way round, so it cannot flatter this side of the comparison.

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

`train.py`'s defaults are small on purpose, so that a run finishes in about a
minute and shows the machinery working. **They are not enough to fit this
model**, and that was measured rather than assumed: the default run took 52
seconds, and the model it produced never scored a candidate above 0.02, so
`run.py` found nothing at all. The head is rebuilt for one class, so it starts
from nothing and needs real training before its confidence number clears the
bar. The numbers below came from the larger settings, written out with them.

The borrowed weights fetch themselves into `weights/` on the first training
run. Neither that file nor the fine-tuned one is committed; delete `weights/`
to start again. `dataset/` and `runs/` are written by training and are not
committed either.

## What it costs

Labels cost nothing. The renderer stamps every pixel with the glass it belongs
to, so an exact outline is a selection over an array it produced anyway. **On
real pictures this is the expensive part of the whole exercise** — somebody
outlines every object in every picture by hand, slowly, and no two people draw
the same outline — so any judgement about whether fine-tuning is worth its
price here has to carry that difference with it.

Training time is real and modest, because the model starts from somebody else's
numbers rather than from random ones. It runs on this machine's integrated
graphics through PyTorch's MPS backend; there is no NVIDIA card here and none
is needed.

The licence is the expensive part, and this solution carries it twice over.
Ultralytics YOLO26-seg is AGPL-3.0, whose network clause reaches a product that
only ever serves answers without shipping the model. A weights file fine-tuned
from an AGPL work is bound by the same terms, so `weights/fine-tuned.pt` is not
a clean asset this project owns and cannot be relicensed by having been trained
here. Nothing in the design depends on this particular model.

## Results

**What produced them.** One training run and two scoring runs, all on this
machine, nothing rented:

```
pixi run python 04-yolo-fine-tuned/train.py --scenes 100 --epochs 60
pixi run python 04-yolo-fine-tuned/run.py --scenes 20
pixi run python 04-yolo-fine-tuned/run.py --scenes 20 --crowded
```

The training run drew 100 scenes from below the bench's dividing line, 50
spawned and 50 crowded, three pictures each. 75 of those scenes went into the
fit, which is 225 pictures holding 1034 outlines, and 25 were kept back for the
run to check itself on. Starting weights `yolo26n-seg.pt`, pictures letterboxed
to 320, batch 8, seed 0, Ultralytics' own default augmentation, on the GPU
through MPS. **It took 39 minutes.** The run's own check on its 75 held-back
pictures reached a mask mAP50 of 0.995, which is not a score of this solution —
those pictures are below the dividing line — only evidence that the fit
converged.

Both scoring runs use the bar at 0.25 and the overlap at 0.7, 20 held-out
scenes from each family, three stations each.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **92** | **66** |
| missed | 8 | 35 |
| merged / split / false | 0 / 0 / 0 | 1 / 0 / 0 |
| position error, median · worst | 3.5 · 42.6 mm | 0.5 · 42.3 mm |
| doubted: width outside what the kind can be | 73 | 106 |

### What the pair measures

This is the number the two solutions exist to produce. Same model, same
starting file, same pictures, same scorecard; one is trained here and one is
not.

| found, of the glasses put out | solution 3, untrained | solution 4, trained here | the bench's floor |
|---|---|---|---|
| spawned | 10 of 100 | **92 of 100** | 100 of 100 |
| crowded | 4 of 101 | **66 of 101** | 83 of 101 |
| position error, median (spawned) | 28.1 mm | 3.5 mm | 6.3 mm |

**That gap is what fine-tuning bought**, and nothing else can be blamed for it.
Solution 3 does find things in these pictures; it calls them sports balls and
frisbees, and the filter on borrowed names drops them. With one class there is
no name to be dropped, and the domain gap is closed by construction because the
weights were fitted on these very pictures.

Three things about the table are worth reading carefully.

**On crowded scenes the floor is 83, not 101.** Eighteen of those glasses are
completely hidden from every station, so no method of any kind can report them.
This solution's 66 is 17 short of what was there to find, not 35.

**The median position error being below the floor's is not a better-than-perfect
result.** The two medians are taken over different sets of glasses. The floor
reports every glass, including ones a station saw only a sliver of, where even
an exact mask gives a poor place — its own worst error is 46.5 mm. This solution
reports 92, and the width refusal removes exactly the cases whose mask was cut
off at the frame edge, so what is left is the better-seen subset.

**The refusals are the coarse outline, not false objects.** Measured over eight
held-out spawned scenes: 92 candidates kept, 11 refused as too narrow and every
one of those had a mask touching the frame edge, and 20 refused as too wide —
and all 20 of those masks mostly cover exactly one real glass. So nothing the
model found was table or nothing; what the check catches is a mask of one real
glass whose edge read too generously or was clipped, which is the limit the
document says training does not touch. The three overlapping stations are what
keep that from costing the glass: it is usually reported from a station that saw
it whole.

At run time the model costs 0.089 s a picture, measured over ten passes with the
model already loaded, so a whole 20-scene run is a few seconds of model time.
The cost of this solution sits almost entirely in building it.

## What training did not fix

- **The outline is still coarse.** The model does not draw an outline pixel by
  pixel; it computes a short list of coarse patterns once for the picture and
  returns a weighted sum of them per object, cut at a threshold and enlarged.
  Training closes the domain gap. It does not make the mask's edge fine, it
  does not give a thin stem back, and the width the shared arithmetic reads off
  that edge carries an error that does not average away.
- **The masks are still modal.** They mark only pixels where the camera saw the
  object, so a glass standing partly behind another is reported as a smaller
  glass in the wrong place. The labels have the same limit the output does, so
  training on them cannot repair it; training towards the whole silhouette
  instead is [solution 6](../../docs/02-segment-glasses/solutions/06-rf-detr-fine-tuned.md)'s
  choice, and `fit` refuses `amodal=True` rather than pretend otherwise.
- **A completely hidden glass is still invisible.** The arrangement with the
  hidden glass and the arrangement without it render to the same picture, pixel
  for pixel, and no model can return two answers for one input. The cure is
  outside every solution here, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **The weights are a narrow asset.** They describe a world of shaded depth
  pictures of opaque glasses in this cell. Change the camera, the shading or
  the range a kind is drawn from and the file is quietly out of date in a way
  no test of the code would notice.
