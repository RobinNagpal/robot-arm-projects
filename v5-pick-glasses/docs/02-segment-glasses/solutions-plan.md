# Plan — the six solutions for problem 2

Short notes only. Each line is a decision, not an explanation. The documents
themselves carry the reasoning.

## The destination, the same for all six

For each glass: **the pixels that are it, and its pose on the table.**

Already returned by the shared arithmetic, which gives a place, a width and the
pixels whose depth readings were used. No code change needed for the output.

**The models give no pose.** They give masks. Depth plus the camera's own pose
turn a mask into a place, by arithmetic shared by all six. A glass stands
upright, so its pose is a position.

## The comparability contract

Three things are shared, and nothing else is. This is what makes the six
comparable.

**Same input.** One fixed set of held-out scenes from the shared bench, same
seeds for every car. Per scene, the survey pictures from the overlapping
stations: the grey picture shaded from depth, the depth reading per pixel, and
the camera pose. Nothing else. **No car may read the spawn record at run time.**

**Same output.** One record per glass: its mask pixels, its place on the table,
its width. One shared function turns a mask into a place and a width, so a
difference in the result belongs to the mask.

**Same yardstick.** One scorecard for all six, plus the exact-mask floor as the
ceiling any car could reach.

## Naming

| Old | New |
|---|---|
| `docs/02-segment-glasses/` | `docs/02-segment-glasses/` |
| `images/02-segment-glasses/` | `images/02-segment-glasses/` |
| `images/generators/02-segment-glasses/` | `images/generators/02-segment-glasses/` |
| `problem-2-sim/` | `02-segment-glasses-sim/` |

Documents:

- `problem.md` — the problem, the input, the output
- `the-bench.md` — scenes, pictures, scorecard, floor. The setup.
- `hidden-glasses.md` — blind regions, pose vetoes, learned ranker. Shared.
- `solutions/overview.md` — the comparison
- `solutions/01-rules-on-the-table.md`
- `solutions/02-train-from-scratch.md`
- `solutions/03-yolo-zero-shot.md`
- `solutions/04-yolo-fine-tuned.md`
- `solutions/05-sam2-with-a-keeper.md`
- `solutions/06-rf-detr-fine-tuned.md`

Numbered by the ladder, least fitted first, so the table reads downwards.

## The six

| # | Car | Fitted | Libraries and models | Licence |
|---|---|---|---|---|
| 1 | Rules on the table | nothing | NumPy, OpenCV | — |
| 2 | Network trained here from scratch | all, here | PyTorch, small convolutional net | — |
| 3 | Borrowed model as it downloads | nothing | Ultralytics YOLO26-seg | AGPL |
| 4 | Same model, fine-tuned here | all, here | Ultralytics YOLO26-seg | AGPL |
| 5 | Promptable foundation model, small fitted head | head only | SAM 2 via `transformers`, scikit-learn | permissive |
| 6 | Transformer segmenter, fine-tuned | all, here | RF-DETR-Seg | Apache 2.0 |

Three carry a second rung inside them:

- **2** — labels from the answer key, or from the arm's own movement.
- **5** — SAM 2 with a grid of points and a keeper, or SAM 3 with a word
  and no keeper.
- **6** — masks trained on visible pixels, or on the whole silhouette.

## One shared document, not a car

Hidden glasses and where to look next: blind regions, pose vetoes, learned
ranker. Unchanged in approach. All six point at it.

## Block at the top of every document

- **What it uses** — libraries, and the model if there is one
- **What it does** — one paragraph
- **How the output is produced** — picture to list of glasses
- **How it differs from the other five** — one line each
- **What it costs** — labels, training, hardware, licence

## What the six let us compare

| Question | Hold still, change one thing |
|---|---|
| Does a model beat rules? | 1 against the rest |
| Fit here, or borrow? | 2 against 3–6 |
| **What does training buy?** | **3 against 4 — same model, same library** |
| Small head, or whole model? | 5 against 4 and 6 |
| Does architecture matter once trained? | 4 against 6 |
| Does predicting the hidden part help? | inside 6 |

## Scorecard: what to add

Place error saturates. Two fine-tuned segmenters already sit within half a
millimetre of the exact-mask floor, and share its worst case. So add:

- **mask overlap per glass** — share of the true silhouette captured
- **mask leak per glass** — share of the mask that is not that glass
- **both broken down by kind** — the stemmed kind is the hard one

The matcher already computes the overlap share to assign a report to a glass.
It is discarded. Recording it is small work.

## Harder scenes, in order of cost

1. **More crowding** — more glasses, closer, bigger height differences.
   Cheapest. Already proven to spread the cars.
2. **A kind outside the borrowed vocabulary** — splits untrained from trained
   by construction.
3. **A handle** — only when orientation is wanted in the output. It inflates
   the shared width step for every car equally, so it adds common noise rather
   than separating them.

## Code: what goes, what stays

| Folder | Holds | Decision |
|---|---|---|
| `problem-2-programmed` | car 1, rules on the table | delete |
| `problem-2-pretrained` | SAM 1 keeper, Mask R-CNN modal and amodal | delete |
| `problem-2-results` | a README only | delete |
| `problem-2-sim` | the renderer, the scenes, the scorecard | **keep, rename** |
| `problem-2-learned` | car 2's network, and the ranker | **keep, decide** |

Two reasons the last two are not deletions.

**The bench is not a car.** It draws the scenes and keeps the score, so it is
the shared input and the shared yardstick. Deleting it would change the input,
which is the one thing the plan holds fixed.

**`problem-4-learned` imports `problem-2-learned/pipeline.py`** and puts both
`problem-2-sim` and `problem-2-learned` on its path. Deleting either breaks
problem 4's code, which was merged last week.

## Not in this pass

- Four of the six cars are not built. Documents say so, and quote no
  measurement produced by a different model.
- Old measurements belong to SAM 1 and Mask R-CNN. Not reusable for the new
  cars. The exact-mask floor survives: it measures the arithmetic, not a model.

## Milestones

1. Plan, naming, deletion scope. **Check:** dependencies proven.
2. Rename docs and images. Fix every link. **Check:** links resolve, tests pass.
3. `problem.md` and `the-bench.md`. **Check:** input and output stated once.
4. The six solution documents, by agents. **Check:** each against the code and
   against the other five.
5. `hidden-glasses.md`, `overview.md`, `README.md`, by hand. **Check:** the
   comparison table agrees with all six.
6. Diagrams. **Check:** no document points at a picture that contradicts it.
7. Code deletion and renaming. **Check:** problem 4 still runs.

## How the documents get written

Six writer agents, one per solution document. Then four reviewer agents, each
reading documents it did not write, checking against the code and against each
other.

Written by hand, because they must agree with all six: `problem.md`,
`the-bench.md`, `hidden-glasses.md`, `overview.md`, `README.md`.
