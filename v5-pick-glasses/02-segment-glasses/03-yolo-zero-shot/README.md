# Solution 3 — a borrowed model, as it downloads

Ultralytics YOLO26-seg, at the small end of the family, run exactly as it
downloads. The outlines it names as drinking vessels are kept. The names are
thrown away, and the masks go to the bench's shared arithmetic. **Nothing is
fitted here**, so not one number in this folder came from this cell's data.
The reasoning is in
[`docs/02-segment-glasses/solutions/03-yolo-zero-shot.md`](../../docs/02-segment-glasses/solutions/03-yolo-zero-shot.md).
The bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

## The files

- `yolo_zero_shot.py` — loads the model, turns one picture into masks, and
  answers the same `Finder.find(picture, kind)` interface as the other
  solutions. `fit` exists only to refuse: there is nothing to train.
- `drinking_vessels.py` — the filter on the borrowed category names, with the
  accepted names in one place. The name is read once and goes no further.
- `run.py` — runs the held-out scenes and scores them. It writes
  `results.json`.
- `what_it_named.py` — lists every name the model offered, with no filter in
  front of it. The result below turns on this.
- `test_zero_shot.py` — the quick checks. No weights and no network.

## Running it

```
pixi run python 03-yolo-zero-shot/run.py --scenes 20
pixi run python 03-yolo-zero-shot/run.py --scenes 20 --crowded
pixi run python 03-yolo-zero-shot/what_it_named.py --scenes 3
pixi run pytest -q 03-yolo-zero-shot
```

There is no train step. The weights fetch themselves on the first picture into
`weights/`. They are 6.4 MB and not committed. Delete the folder to start
again.

## What it costs

No labels, no training run, no held-out set to fit a bar on, and no graphics
card of its own. Inference runs through the MPS backend at 0.02 s a picture,
measured over ten passes with the model already loaded. A whole 20-scene run
(60 pictures) takes about 6 seconds, including the rendering.

The real cost is the AGPL-3.0 licence.
[The licence](../../docs/02-segment-glasses/solutions/03-yolo-zero-shot.md#the-licence-which-is-the-real-cost-here)
explains what it demands and why it does not matter for this comparison.

## Results — and they are a null result

20 held-out scenes from each family, three stations each, scored by the bench.
The table gives one column per family.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **10** | **4** |
| missed | 90 | 97 |
| merged / split / false | 0 / 0 / 0 | 0 / 0 / 0 |
| position error, median · worst | 28.1 · 36.3 mm | 36.5 · 46.6 mm |
| pictures where it named no drinking vessel | 49 of 60 | 56 of 60 |

For scale, the bench's own floor finds 100 of 100 at 6.3 mm median. The floor
is the same arithmetic on exact masks. So the ten glasses this solution found
are placed four times further out than the floor, and ninety were never
reported.

**It fails on the names, not on the outlines.** The model does find things in
these pictures. It just does not call them drinking vessels. The next table is
`what_it_named.py` over three scenes of each kind, with no filter in front.

| kind | what the model called them | kept by the filter |
|---|---|---|
| straight glass | sports ball 8, frisbee 5, vase 3, person 1 | 3 |
| tapered glass | frisbee 19, sports ball 4, person 1 | 0 |
| stemmed glass | sports ball 12, frisbee 4, bird 2, cake 1, donut 1 | 0 |
| short stemmed glass | frisbee 14, sports ball 10, vase 2 | 2 |

From straight above, a glass is a round silhouette with none of the features
that say "glass" in a photograph. [The domain
gap](../../docs/02-segment-glasses/solutions/03-yolo-zero-shot.md#the-domain-gap-which-is-the-main-risk)
explains this. The nearest round things on the model's list are a sports ball
and a frisbee. The model knows where the objects are. It answers a different
question correctly.

The numbers say two more things. First, the counts are far short of the
glasses present: a handful of detections per picture where four to six glasses
stand. So the naming is not the only gap, though it decides the scorecard.
Second, **nothing is merged, split or false**. Every glass this solution
reported was a real glass. It fails by silence, the hardest failure to notice.

**The filter was not tuned to these names, and must not be.** Adding "sports
ball" and "frisbee" would lift the score at once. It would also fit the filter
on this cell's data, the one thing this solution exists not to do. The right
repair is
[solution 4](../../docs/02-segment-glasses/solutions/04-yolo-fine-tuned.md):
this same model, trained further here, with its names cut to one class. The
gap between the two measures what that training buys. This result sets one end
of it.

## What this does not do

- **No width check.** Every other solution refuses a footprint no glass of the
  kind could have. This one does not, on purpose. Such a check would hide the
  silent failure that solution 4 is compared against. So `find` is handed the
  kind and does not use it.
- **No completion of hidden parts.** The model outlines only pixels where it
  saw the object. A glass half behind another reads as a smaller glass in the
  wrong place, and a fully hidden glass is absent. The cure is outside this
  solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
