# Solution 3 — a borrowed model, as it downloads

Ultralytics YOLO26-seg at the small end of the family, run exactly as it
downloads. The outlines it names as drinking vessels are kept, the names are
thrown away, and the masks go to the bench's shared arithmetic. **Nothing is
fitted here**, so there is not one number in this folder that came from this
cell's data. Its document is
[`docs/02-segment-glasses/solutions/03-yolo-zero-shot.md`](../../docs/02-segment-glasses/solutions/03-yolo-zero-shot.md),
and the bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

## The files

- `yolo_zero_shot.py` — loads the model, turns one picture into masks, and
  answers the same `Finder.find(picture, kind)` interface the other solutions
  do. `fit` exists only to refuse: there is nothing here to train.
- `drinking_vessels.py` — the filter on the borrowed category names, with the
  accepted names in one place. It is read once and the name goes no further.
- `run.py` — the held-out scenes, scored; writes `results.json`.
- `what_it_named.py` — every name the model offered, with no filter in front
  of it. This is the measurement the result below turns on.
- `test_zero_shot.py` — the quick checks. No weights and no network.

## Running it

```
pixi run python 03-yolo-zero-shot/run.py --scenes 20
pixi run python 03-yolo-zero-shot/run.py --scenes 20 --crowded
pixi run python 03-yolo-zero-shot/what_it_named.py --scenes 3
pixi run pytest -q 03-yolo-zero-shot
```

There is no train step. The weights fetch themselves on the first picture into
`weights/`, which is 6.4 MB and not committed; delete the folder to start again.

## What it costs

No labels, no training run, no held-out set to fit a bar on, and no graphics
card of its own. Inference runs on this machine through the MPS backend at
0.02 s a picture, measured over ten passes with the model already loaded, so a
whole 20-scene run (60 pictures) takes about 6 seconds including the rendering.

The real cost is the licence. Ultralytics is AGPL-3.0, and the AGPL's network
clause reaches a product that only ever serves answers from the model without
shipping it. Everything else this project depends on is permissive. Nothing in
the design depends on this particular model, so the method transfers to a
permissively licensed segmenter if it were ever worth carrying forward.

## Results — and they are a null result

20 held-out scenes from each family, three stations each, scored by the bench.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **10** | **4** |
| missed | 90 | 97 |
| merged / split / false | 0 / 0 / 0 | 0 / 0 / 0 |
| position error, median · worst | 28.1 · 36.3 mm | 36.5 · 46.6 mm |
| pictures where it named no drinking vessel | 49 of 60 | 56 of 60 |

For scale, the bench's own floor — the same arithmetic on exact masks — finds
100 of 100 at 6.3 mm median. So of the ten glasses this solution did find, the
places are four times further out than the arithmetic's own limit, and ninety
were never reported at all.

**Why it fails is not the outlines. It is the names.** The model does find
things in these pictures; it simply does not call them drinking vessels.
`what_it_named.py` over three scenes of each kind, with no filter in front of
it:

| kind | what the model called them | kept by the filter |
|---|---|---|
| straight glass | sports ball 8, frisbee 5, vase 3, person 1 | 3 |
| tapered glass | frisbee 19, sports ball 4, person 1 | 0 |
| stemmed glass | sports ball 12, frisbee 4, bird 2, cake 1, donut 1 | 0 |
| short stemmed glass | frisbee 14, sports ball 10, vase 2 | 2 |

A glass seen from straight above is a disc, and in a grey picture shaded from
depth a disc has no transparency, no highlight and no bright rim — none of the
evidence that says "glass" in a photograph. What is left is a round silhouette,
and the nearest things to a round silhouette on the model's list are a sports
ball and a frisbee. The model is not confused about where the objects are. It is
answering a different question correctly.

Two further things the numbers say. The counts are also far short of the glasses
present — a handful of detections per picture where four to six glasses stand —
so the naming is not the only gap, though it is the one that decides the
scorecard. And **nothing is merged, split or false**: every glass this solution
reported was a real glass. It fails by silence, which is the failure the
document warns is the hardest to notice.

**The filter was not tuned to these names, and must not be.** Adding "sports
ball" and "frisbee" to the accepted list would lift the score immediately and
would be fitting the filter on this cell's own data, which is the single thing
this solution exists not to do. The baseline's whole value is that it fits
nothing. The right repair is the one the folder already plans:
[solution 4](../../docs/02-segment-glasses/solutions/04-yolo-fine-tuned.md) is
this same model with its training continued here and its vocabulary cut to one
class, and the gap between the two is a measurement of what that training buys.
This result sets one end of it.

## What this does not do

- **No width check.** Every other solution here refuses a footprint no glass of
  the kind could have. This one does not, deliberately: the document's honest
  summary is that a borrowed model used as the decider fails *silently*, and a
  check the design does not contain would hide the behaviour solution 4 exists
  to be compared against. So `find` is handed the kind and has no use for it.
- **No completion of hidden parts.** The model outlines only pixels where it saw
  the object, so a glass half behind another reads as a smaller glass in the
  wrong place, and a glass completely hidden is absent. The cure is outside this
  solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
