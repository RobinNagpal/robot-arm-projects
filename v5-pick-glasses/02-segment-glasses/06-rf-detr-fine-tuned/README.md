# Problem 2 — RF-DETR-Seg, fine-tuned here

Solution 6 of six. A transformer that detects and segments in one pass,
borrowed already fitted to ordinary labelled pictures and then trained on this
cell's own pictures with the class list cut down to one entry, "glass".

The document is
[`06-rf-detr-fine-tuned.md`](../../docs/02-segment-glasses/solutions/06-rf-detr-fine-tuned.md)
and it carries the explanation. This file says what is here and how to run it.

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

The model carries a fixed number of queries, each of which either reports one
glass or reports nothing, and each query's mask is computed over the whole
picture rather than inside a rectangle. So two glasses whose outlines join are
two slots from the beginning, and a mask has no rectangle to escape.

`--target` chooses what the masks are trained against, and that is the whole
difference between the two rungs:

- `modal` — the pixels the camera can see of a glass.
- `amodal` — the glass's **whole silhouette**, which the bench renders by
  drawing the scene again with the other glasses taken away. The labels cost
  one more render and no judgement, which is true in a simulator and in no
  other setting.

## The trap, which is what most of the code is about

A mask covering a whole silhouette claims pixels where the camera saw the glass
in front of it. **The depth reading at such a pixel belongs to that other
glass**, so feeding it into the shared arithmetic drags the computed place
across the gap and onto the glass in front — and nothing objects, because the
mask looks better, the footprint stays round and the width stays legal.

So every mask is split before the arithmetic runs, and
`masks_to_glasses.one_glass` is handed the asserted pixels and leaves their
readings out.

**How the split is read off the answer.** A camera looking straight down throws
every outline outwards from the point below it, so of two reports whose masks
overlap, the one standing nearer that point is the one in front. Every pixel
two reports both claim therefore belongs to whichever stands nearer the point
below the camera, and the other must call it asserted. Nothing in that needs
the truth: each report's place comes from the pixels no other report claims,
and the point below the camera comes from the camera's own pose.

Measured the way `bench/floor.py --crowded` measures it, over 20 crowded
held-out scenes and the 133 partly hidden glasses in them, with the bench's own
exact silhouettes and no model anywhere in the chain:

| the asserted pixels are | place of a partly hidden glass |
|---|---|
| named by the bench, which knows the answer | 12.2 mm median, 51.3 mm worst |
| named by this split, worked out from the answer | 12.2 mm median, 51.3 mm worst |
| fed in with the rest | 46.1 mm median, 130.5 mm worst |

The last line is the trap. `test_rf_detr_seg.py` holds both measurements, so a
change that quietly starts feeding asserted pixels in fails the tests.

The split agrees with the exact one to the tenth of a millimetre, and the
asserted part it names overlaps the true hidden part completely for more than
half the glasses. Not for all of them: where two glasses of the same kind stand
at almost the same distance from the point below the camera, which of them is
in front is decided by a few millimetres, and the split can get it the wrong
way round. It then gives away pixels it should have kept, which costs width and
never poisons a place.

**What the split cannot see** is a glass hidden by something the model never
reported. There is nothing in the picture to work that out from either, and it
is the same boundary [looking again at what was
hidden](../../docs/02-segment-glasses/hidden-glasses.md) exists for.

## The two checks, each of which can only refuse

- **The width must lie inside the range the kind allows.** One region over two
  glasses is wider than any glass of the kind can be. This is the loud failure
  the quiet one is traded against.
- **The asserted part must lie where the camera could not see.** A mask
  claiming glass across a patch the camera had a clear view of, where the
  reading comes back off a surface standing further away than the kind's widest
  footprint, is contradicting an observation. Its share is held below
  `masks_to_glasses.SPREAD`'s own tail, so the two checks do different work.

A glass failing either is reported as doubtful, with the reason, and the reason
says as well whether the glass ran off the edge of the frame. That turns out to
be the whole story about false refusals. Handed the bench's own exact
silhouettes on 20 held-out scenes — the best masks that exist, so every refusal
here is a false one:

| | spawned | crowded |
|---|---|---|
| reported | 73.3% | 74.3% |
| refused, and the glass ran off the edge of the frame | 26.7% | 22.8% |
| refused with the whole glass in frame | **0.0%** | **2.3%** |

At the cell's own survey height one picture does not hold the glass zone, so a
glass at the far side of a station's frame is cut in half and the width read
off it is not the glass's width. The survey stands at three overlapping
stations for exactly this: a glass cut off in one picture sits well inside
another's, and `run.py` keeps the report from the station the glass stood
nearest the middle of.

Every report carries its **visible fraction**, the observed share of its own
mask, because every consumer further down has its own tolerance for how much of
an answer was asserted and none of them can apply it once the two parts have
been merged.

## Running it

```
pixi run python 06-rf-detr-fine-tuned/weights.py                       # fetch the borrowed weights
pixi run python 06-rf-detr-fine-tuned/train.py --target amodal         # the slow step
pixi run python 06-rf-detr-fine-tuned/run.py --target amodal --crowded
pixi run pytest -q 06-rf-detr-fine-tuned
```

`--target modal` does the same for the first rung. The two are saved apart,
`weights/fitted-modal.pth` and `weights/fitted-amodal.pth`, because scoring one
fit and calling it the other would be the easiest mistake in the folder.

## What it costs

- **The borrowed weights** are 128 MB, fetched once into `weights/roboflow/`.
  They are the one thing here that needs the network, and no test touches them.
- **The labels are free**, as the document says: the bench renders which glass
  owns each pixel, and the whole silhouette costs one more render per glass.
- **The fine-tune** is the largest cost. It runs here, on this machine's
  graphics processor through PyTorch's MPS backend; there is no NVIDIA card and
  no CUDA. The measured times are in the table below.
- **Running it** is cheap: one pass over one picture is a small fraction of the
  seconds an arm movement costs.

| | measured here |
|---|---|
| fetching the borrowed weights | 128 MB, a few seconds |
| fine-tuning `modal`, 60 scenes (180 pictures), 10 epochs | 932 s |
| one picture through the fitted model | about a second |

The machine is an Apple M4 with no NVIDIA card. It was shared with other
training runs throughout, so these are upper bounds rather than the model's own
times. No accelerator had to be rented: a fine-tune of this size fits on the
laptop, which is the whole argument for fine-tuning rather than starting from
random numbers.

## Results

Both rungs are scored on the bench's 20 held-out scenes, which no fine-tune
here has seen. Beside each is the **floor**: the same arithmetic handed the
masks the renderer itself drew, which no segmenter can improve on.
`bench/floor.py --scenes 20` and `--scenes 20 --crowded` produce the floor rows.

### Spawned layouts, 20 scenes, 100 glasses

| | found | missed | merged | split | false | place | covered | not the glass |
|---|---|---|---|---|---|---|---|---|
| `modal` | 90 | 10 | 0 | 0 | 0 | 4.2 mm median, 42.2 worst | 96.8% | 0.0% |
| the floor, exact masks | 100 | 0 | 0 | 0 | 0 | 6.3 mm median, 46.5 worst | 100% | 0.0% |

By kind, `modal` covered 96.8% of a straight glass, 97.3% of a tapered one,
96.4% of a stemmed one and 95.7% of a short stemmed one, and claimed 0.0–0.1%
of pixels that were not the glass. All four kinds come out within two points of
each other, stem included, which is what [the test
bench](../../docs/02-segment-glasses/the-bench.md) says to expect of a solution
fitted on this cell's own pictures and not of one built from written rules.

The ten missed glasses are not masks the model got wrong. They are glasses
refused at every station they appeared in, and 88 of the 90 refusals in that
run say the glass ran off the edge of a frame. That also explains the one line
where this solution beats the floor: `bench/floor.py` applies no checks at all,
so it keeps the reports from cut-off masks that are refused here, and a report
read off half a glass is what a place 6.3 mm out is made of. The trade is the
project's own: a refused glass is a result, a wrongly placed one is not.

### Crowded layouts, 20 scenes, 101 glasses

| | found | missed | merged | split | false | place |
|---|---|---|---|---|---|---|
| `modal` | 74 | 27 | 2 | 1 | 0 | 0.5 mm median, 58.4 worst |
| the floor, exact visible masks | 83 | 18 | 1 | 1 | 0 | 0.4 mm median, 50.0 worst |
| the floor, whole masks with the asserted pixels named | 83 | 18 | 1 | 1 | 0 | 0.4 mm median, 50.0 worst |
| the floor, the same masks fed in whole | 69 | 32 | **14** | 2 | 0 | 0.1 mm median, 72.7 worst |

The last floor row is the trap again, in the counts rather than in one glass's
place: feeding the asserted pixels in turns 1 merged report into 14 and loses
14 glasses, with exact masks and no model anywhere. That is the row this
folder's split exists to stay off.

`modal` covered 97.4% of each glass it reported here and claimed 0.0% that was
not the glass, which is the same quality as on the easy layouts; what crowding
costs it is glasses it never reports at all, not outlines it draws badly.

The split is doing work on this run even though the target is the visible
pixels. 152 of its 275 reports had an asserted part named and left out, and the
least visible of them was 11% observed — a predicted mask bleeds over the glass
in front of it whether or not it was trained to, and the reading under the
bleed belongs to that other glass either way. So the first rung needs the split
as well; the second rung only needs it more.

### The amodal rung

**Not scored.** The fine-tune was started with the same settings as `modal` and
reached epoch 4 of 10, with validation segmentation mAP@50:95 rising 0.725 →
0.760 → 0.814 → 0.826. A dozen other training runs then filled the machine, the
run fell to a few per cent of one core, and it was stopped unfinished. No
`results-amodal.json` is written and no amodal score is claimed here.

What *is* measured about that rung is its split, in the table further up: exact
to the tenth of a millimetre against the answer the bench knows. What is not
measured is how well the model draws a whole silhouette in the first place.

The chain itself has been run end to end on that target, with a one-epoch
fine-tune, so what is missing is the training time and not any of the code:
that model found nothing, which is what a one-epoch model does, and it found
nothing without complaining about anything either.

Run `make train TARGET=amodal` followed by `make crowded TARGET=amodal` on a
quiet machine to fill the numbers in. On the evidence of `modal`, which reached
validation segmentation mAP 0.902 in 932 s, it is about a quarter of an hour.
Nothing has to be rented for it.
