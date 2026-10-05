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
| `02-segment-glasses/bench/` | `02-segment-glasses-sim/` |

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
| **What does training buy?** | **3 against 4 — same model, same library, same starting weights. Training also cuts the category list to one class, which cannot be had separately, so nothing varies that the training did not bring.** |
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
| `02-segment-glasses/bench` | the renderer, the scenes, the scorecard | keep, rename |
| `02-segment-glasses/01-rules-on-the-table` | **solution 1 as written** | keep |
| `02-segment-glasses/02-train-from-scratch` | **solution 2's network**, and the ranker | keep |
| `02-segment-glasses/results` | the two pipelines compared | keep |
| `02-segment-glasses/05-sam2-with-a-keeper` | shared pieces **and** two superseded models | split |

An audit cut this list down. Only one folder holds anything dead.

**`02-segment-glasses/01-rules-on-the-table` is solution 1.** Its finding step
groups points where they stand on the table rather than where they fall in the
picture, which is solution 1's method exactly. It is not superseded by anything.

**`02-segment-glasses/02-train-from-scratch` is solution 2.** Its network is the
one solution 2 describes as already written, and `problem-4-learned` imports it.

**`02-segment-glasses/results` is cited from outside.** Problem 4's documents
point at its comparison in three places.

**The bench is used by three problems**, not one: problems 2, 3 and 4 all put
it on their path. Deleting it would change the input the six are compared on,
which is the one thing this plan holds fixed.

### Splitting `02-segment-glasses/05-sam2-with-a-keeper`

It holds the shared pieces as well as two superseded models. The shared ones
belong in the bench; only the models go.

| Move to the bench | Why |
|---|---|
| the mask-to-place arithmetic | the shared final step; a difference must belong to the mask |
| the station layout and picture assembly | the shared input |
| the exact-mask floor | the yardstick every car is read against |
| the per-kind mask measurement | the number that separates cars when place cannot |

| Delete | Why |
|---|---|
| the SAM 1 keeper | solution 5 uses SAM 2 |
| the Mask R-CNN segmenter, modal and amodal | solution 6 uses RF-DETR-Seg |
| its training and weights helpers | belong to the two deleted models |

## Not in this pass

- Four of the six cars are not built. Documents say so, and quote no
  measurement produced by a different model.
- Old measurements belong to SAM 1 and Mask R-CNN. Not reusable for the new
  cars. The exact-mask floor survives: it measures the arithmetic, not a model.

## Diagrams: reuse, do not rewrite

The six writers asked for 79 pictures between them. 95 already exist, drawn for
the old solutions, and most depict ideas that survive. Each generator runs to
well over a thousand lines, so writing 79 fresh ones is the wrong move.

| Existing generator | Where its pictures go now |
|---|---|
| cluster on the table | solution 1 |
| the network, and the voting | solution 2 |
| self-supervised from movement | solution 2, second rung |
| segment anything | solution 5 |
| the fine-tuned segmenter | solutions 4 and 6 |
| amodal masks | solution 6, second rung |
| move the camera, choosing the next look | the shared look-again document |
| split the blob | mostly stale; its splay and merge panels suit `problem.md` |

### Two kinds of rejection, and only one is a deletion

A picture put back into a document is judged against what that document now
says, so many were rejected. The reasons divide, and the division decides what
happens to the file.

**Rejected on substance — delete.** The picture draws a camera looking from the
side where the survey looks from the top, or a method none of the six
describes, or it argues the opposite of what the problem statement says. No
amount of relabelling saves these.

**Rejected on labels only — relabel and redraw.** The picture is exactly right
and says "SAM" where the document says SAM 2, or labels itself "solution 8"
where it is now solution 5, or carries a caption about an earlier version of a
page. The generator that drew it still exists, so the label is a line of code
to change and the picture can be redrawn and placed. These are the valuable
ones: several were rejected only because a word in the image names the wrong
generation.

New pictures are needed only where the material is new:

- how a borrowed model builds a coarse outline, and its fixed category list;
- a transformer segmenter's queries, and set prediction against pruning;
- the untrained-against-trained pair, side by side;
- the ladder of how much is fitted, as one picture.

## Milestones

1. Plan, naming, deletion scope. **Check:** dependencies proven.
2. Rename docs and images. Fix every link. **Check:** links resolve, tests pass.
3. `problem.md` and `the-bench.md`. **Check:** input and output stated once.
4. The six solution documents, by agents. **Check:** each against the code and
   against the other five.
5. `hidden-glasses.md`, `overview.md`, `README.md`, by hand. **Check:** the
   comparison table agrees with all six.
6. Diagrams: remap and renumber what exists, then draw only the gaps.
   **Check:** no document points at a picture that contradicts it.
7. Move the shared pieces into the bench. **Check:** the floor still runs.
8. Delete the car code, rename the folders. **Check:** problem 4 still runs.

## How the documents get written

Six writer agents, one per solution document. Then four reviewer agents, each
reading documents it did not write, checking against the code and against each
other.

Written by hand, because they must agree with all six: `problem.md`,
`the-bench.md`, `hidden-glasses.md`, `overview.md`, `README.md`.
