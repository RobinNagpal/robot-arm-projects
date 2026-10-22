# Problem 2 — RF-DETR-Seg, fine-tuned here

Solution 6 of six. A transformer that detects and segments in one pass. It
arrives fitted to ordinary labelled pictures. Then it is trained on this cell's
pictures with one class, "glass".

The reasoning is in
[`06-rf-detr-fine-tuned.md`](../docs/solutions/06-rf-detr-fine-tuned.md).
This file says what is here, how to run it, and what it produced.

## What is here

| File | What it is |
|---|---|
| `rf_detr_seg.py` | the model: `fit`, `load`, and a `Finder` answering `find(picture, kind)` |
| `labels.py` | the bench's scenes written out as the COCO folder the package trains from |
| `weights.py` | where the borrowed weights and the fitted ones live |
| `train.py` | the fine-tune, with the modal / amodal flag |
| `run.py` | the held-out scenes, the shared scorecard, and `results-<target>.json` |
| `test_rf_detr_seg.py` | the quick checks: no weights, no network, no fine-tune |
| `Makefile` | `make fetch`, `make train`, `make run`, `make crowded`, `make test` |

## The two rungs

Each mask is computed over the whole picture, not inside a rectangle. [What a
transformer segmenter does
differently](../docs/solutions/06-rf-detr-fine-tuned.md#what-a-transformer-segmenter-does-differently)
explains why that matters.

`--target` chooses what the masks are trained against. That is the only
difference between the two rungs:

- `modal` — the pixels the camera can see of a glass.
- `amodal` — the glass's **whole silhouette**. The bench renders it by drawing
  the scene again with the other glasses removed. The label costs one more
  render and no judgement.

## The trap, which is what most of the code is about

A whole-silhouette mask claims pixels where the camera saw the glass in front.
The depth reading there belongs to that other glass. Feeding it in drags the
place onto the glass in front, and nothing objects. [The
trap](../docs/solutions/06-rf-detr-fine-tuned.md#the-trap-and-it-is-the-one-thing-most-easily-got-wrong)
explains it in full.

So every mask is split before the arithmetic runs. `masks_to_glasses.one_glass`
gets the asserted pixels and leaves their readings out.

**How the split is read off the answer.** Of two overlapping reports, the one
nearer the point below the camera is in front, and it owns the shared pixels.
[The code at the heart of
it](../docs/solutions/06-rf-detr-fine-tuned.md#the-code-at-the-heart-of-it)
shows the function. It needs no truth: each report's place comes from the
pixels no other report claims, and the point below the camera comes from the
camera's pose.

The table below is measured the way `bench/floor.py --crowded` measures it. It
covers 20 crowded held-out scenes and the 133 partly hidden glasses in them. It
uses the bench's own exact silhouettes, with no model in the chain. Each row is
one way of handling the asserted pixels.

| the asserted pixels are | place of a partly hidden glass |
|---|---|
| named by the bench, which knows the answer | 12.2 mm median, 51.3 mm worst |
| named by this split, worked out from the answer | 12.2 mm median, 51.3 mm worst |
| fed in with the rest | 46.1 mm median, 130.5 mm worst |

The last line is the trap. `test_rf_detr_seg.py` holds both measurements. A
change that starts feeding asserted pixels in fails the tests.

The split matches the exact one to the tenth of a millimetre. For more than
half the glasses, the asserted part it names covers the true hidden part
completely. Not for all: two glasses of one kind may stand at almost the same
distance from the point below the camera. Then a few millimetres decide which
is in front, and the split can get it backwards. It then gives away pixels it
should keep. That costs width but never spoils a place.

**What the split cannot see** is a glass hidden by something the model never
reported. Nothing in the picture shows that. [Looking again at what was
hidden](../docs/hidden-glasses.md) exists for it.

## The two checks, each of which can only refuse

[The risk of inventing
glass](../docs/solutions/06-rf-detr-fine-tuned.md#the-risk-of-inventing-glass-and-what-bounds-it)
explains both checks. In the code:

- **The width must lie inside the range the kind allows, unless the picture ran
  out before the glass did.** A mask at the frame edge may hold only half a
  glass. `_width_refuses` reads `masks_to_glasses.Found.cut_off` and does not
  refuse those.
- **The asserted part must lie where the camera could not see.** Its share is
  held below `masks_to_glasses.SPREAD`'s own tail, so the two checks do
  different work.

A glass failing either is reported as doubtful, with the reason. The reason also
says whether the glass ran off the frame edge. **The frame explains almost every false
refusal.** The table below hands the checks the bench's exact silhouettes on 20
held-out scenes. These are the best masks that exist, so every refusal is a
false one. Each glass a station saw any pixel of is counted once.

| | spawned: before · after | crowded: before · after |
|---|---|---|
| reported | 73.3% · **87.0%** | 76.8% · **87.9%** |
| refused, and the glass ran off the edge of the frame | 26.7% · 13.0% | 20.1% · 9.0% |
| refused with the whole glass in frame | 0.0% · 0.0% | 3.1% · 3.1% |

"Before" is the width check on every report. "After" is the same check reading
`cut_off` first. Half the false refusals go. The ones left all run off the
frame for another reason: too little of the glass was in frame to place, or
the mask claims glass where the camera saw past it. No refusal with the whole
glass in frame changes, so the check still does its own work.

The survey uses three overlapping stations for this reason. A glass cut off in
one picture sits well inside another. `run.py` keeps the report from the
station whose middle the glass stood nearest.

Every report carries its **visible fraction**, the observed share of its own
mask. [What the completion actually
buys](../docs/solutions/06-rf-detr-fine-tuned.md#what-the-completion-actually-buys)
says why.

## Running it

```
pixi run python 06-rf-detr-fine-tuned/weights.py                       # fetch the borrowed weights
pixi run python 06-rf-detr-fine-tuned/train.py --target amodal         # the slow step
pixi run python 06-rf-detr-fine-tuned/run.py --target amodal --crowded
pixi run pytest -q 06-rf-detr-fine-tuned
```

`--target modal` does the same for the first rung. The two fits are saved
apart, as `weights/fitted-modal.pth` and `weights/fitted-amodal.pth`. Scoring
one fit and calling it the other would be the easiest mistake in the folder.

## What it costs

- **The borrowed weights** are 128 MB, fetched once into `weights/roboflow/`.
  They are the only thing here that needs the network. No test touches them.
- **The labels are free.** The bench renders which glass owns each pixel. The
  whole silhouette costs one more render per glass.
- **The fine-tune** is the largest cost. It runs on this machine's graphics
  processor through PyTorch's MPS backend. There is no NVIDIA card and no CUDA.
- **Running it** is cheap: one picture takes a small part of the seconds an arm
  movement takes.

The table below gives the times measured here.

| | measured here |
|---|---|
| fetching the borrowed weights | 128 MB, a few seconds |
| fine-tuning `modal`, 60 scenes (180 pictures), 10 epochs | 932 s |
| one picture through the fitted model | about a second |

The machine is an Apple M4 with no NVIDIA card. Other training runs shared it
the whole time, so these times are upper bounds. Nothing had to be rented. A
fine-tune of this size fits on the laptop.

## Results

Both rungs are scored on the bench's 20 held-out scenes. No fine-tune here has
seen them. Beside each is the **floor**: the same arithmetic given the
renderer's own masks, which no segmenter can beat. `bench/floor.py --scenes 20`
and `--scenes 20 --crowded` produce the floor rows. [The
results](../results/README.md) compare all six solutions.

### Spawned layouts, 20 scenes, 100 glasses

Each row is one set of masks. The columns are the examiner's counts and
measures.

| | found | missed | merged | split | false | place | covered | not the glass |
|---|---|---|---|---|---|---|---|---|
| `modal` | 96 | 4 | 0 | 0 | 0 | 4.5 mm median, 42.2 worst | 96.7% | 0.0% |
| the floor, exact masks | 100 | 0 | 0 | 0 | 0 | 6.3 mm median, 46.5 worst | 100% | 0.0% |

By kind, `modal` covered 96.8% of a straight glass, 97.3% of a tapered one,
96.4% of a stemmed one and 96.1% of a short stemmed one. It claimed 0.0–0.1% of
pixels that were not the glass. All four kinds are within two points of each
other, stem included. [The test
examiner](../docs/the-examiner.md) expects that of a
solution fitted on this cell's pictures.

The four missed glasses are not bad masks. They were refused at every station
they appeared in. 42 of the 44 refusals in that run say the glass ran off a
frame edge. Only 2 of the 44 are the width check with the whole glass in frame.

### Crowded layouts, 20 scenes, 101 glasses

The rows are read the same way as above.

| | found | missed | merged | split | false | place |
|---|---|---|---|---|---|---|
| `modal` | 78 | 23 | 3 | 2 | 0 | 0.5 mm median, 58.4 worst |
| the floor, exact visible masks | 83 | 18 | 1 | 1 | 0 | 0.4 mm median, 50.0 worst |
| the floor, whole masks with the asserted pixels named | 83 | 18 | 1 | 1 | 0 | 0.4 mm median, 50.0 worst |
| the floor, the same masks fed in whole | 69 | 32 | **14** | 2 | 0 | 0.1 mm median, 72.7 worst |

The last floor row is the trap again, this time in the counts. Feeding the
asserted pixels in turns 1 merged report into 14 and loses 14 glasses. That is
with exact masks and no model. The split exists to avoid that row.

`modal` covered 97.3% of each glass it reported and claimed 0.0% that was not
the glass. That is the same quality as on the easy layouts. Crowding costs it
glasses it never reports, not outlines it draws badly.

The split does work even on the visible target. 185 of its 272 reports had an
asserted part named and left out. The least visible was 11% observed. A
predicted mask bleeds over the glass in front, even when not trained to. The
reading under the bleed belongs to that other glass. So the first rung
needs the split too; the second rung needs it more.

### What not refusing on a cut-off mask was worth

Same weights, settings and scenes, with `_width_refuses` reading `cut_off`
first. Each cell gives before · after.

| | spawned: before · after | crowded: before · after |
|---|---|---|
| **found, of the glasses put out** | 90 · **96** of 100 | 74 · **78** of 101 |
| missed | 10 · **4** | 27 · **23** |
| merged / split | 0 / 0 · 0 / 0 | 2 / 1 · 3 / 2 |
| place, median · worst | 4.2 · 42.2 mm · 4.5 · 42.2 mm | 0.5 · 58.4 mm · 0.5 · 58.4 mm |
| refused on width, mask off the frame edge | 71 · **0** | 62 · **0** |
| refused on width, whole glass in frame | 2 · 2 | 15 · 15 |
| refused for claiming glass past a clear view | 14 · 39 | 3 · 36 |
| refused for too little of it to place | 3 · 3 | 5 · 8 |

Ten glasses came back. The price was one more merged and one more split report
on the crowded layouts. The place did not move. **Every width refusal that went
was on a mask the frame had cut short.** The refusals with the whole glass in
frame (2 spawned, 15 crowded) are untouched.

The other two rows move because a report refused on width used to stop there.
Now it goes on to the clear-view check, and some fail that instead. That is the
stronger check, since it is geometry on the kind's own limits.

### The amodal rung

**Not scored.** The fine-tune used the same settings as `modal`. It reached
epoch 4 of 10, with validation segmentation mAP@50:95 rising 0.725 → 0.760 →
0.814 → 0.826. Then a dozen other training runs filled the machine. The run
fell to a few per cent of one core and was stopped. No `results-amodal.json` is
written and no amodal score is claimed.

What *is* measured for that rung is its split, in the trap table above: exact
to the tenth of a millimetre. What is not measured is how well the model draws
a whole silhouette.

The chain has run end to end on that target with a one-epoch fine-tune. So
only training time is missing, not code. That model found nothing, as a
one-epoch model does, and raised no errors.

Run `make train TARGET=amodal` and then `make crowded TARGET=amodal` on a quiet
machine to fill the numbers in. `modal` reached validation segmentation mAP
0.902 in 932 s, so this should take about a quarter of an hour. Nothing has to
be rented.
