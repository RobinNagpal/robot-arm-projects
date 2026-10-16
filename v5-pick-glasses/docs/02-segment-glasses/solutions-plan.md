# Plan — the six solutions for problem 2

Short notes only. Each line is a decision, not an explanation. The reasoning is
in the documents themselves. This is the plan as written before the six were
built. All six are now built and scored; see the [results
page](../../02-segment-glasses/results/README.md).

## The destination, the same for all six

For each glass: **the pixels that are it, and its place on the table.** [The
problem](problem.md#what-must-come-out) defines this output.

The shared step already returns a place, a width and the pixels it used. No code
change is needed for the output.

**The models give no pose, only masks.** The shared step turns a mask into a
place. See [the examiner](the-examiner.md#what-must-come-back).

## The comparability contract

The six share the same input, the same output and the same yardstick, and
nothing else. [The examiner](the-examiner.md#why-there-is-an-examiner-at-all)
holds all three fixed. Two rules from it matter most here:

- **No car may read the spawn record at run time.**
- One shared function turns a mask into a place and a width, so a difference in
  the result belongs to the mask.

The exact-mask floor is the best any car could reach.

## Naming

The table maps the old names to the new ones.

| Old | New |
|---|---|
| `docs/02-segment-glasses/` | `docs/02-segment-glasses/` |
| `images/02-segment-glasses/` | `images/02-segment-glasses/` |
| `images/generators/02-segment-glasses/` | `images/generators/02-segment-glasses/` |
| `02-segment-glasses/bench/` | `02-segment-glasses-sim/` |

The last rename was not done. The bench is still in `02-segment-glasses/bench/`.

Documents:

- `problem.md` — the problem, the input, the output
- `the-examiner.md` — scenes, pictures, scorecard, floor. The setup.
- `hidden-glasses.md` — blind regions, pose vetoes, learned ranker. Shared.
- `solutions/overview.md` — the comparison
- `solutions/01-rules-on-the-table.md`
- `solutions/02-train-from-scratch.md`
- `solutions/03-yolo-zero-shot.md`
- `solutions/04-yolo-fine-tuned.md`
- `solutions/05-sam2-with-a-keeper.md`
- `solutions/06-rf-detr-fine-tuned.md`

They are numbered from least fitted to most fitted, so the table reads
downwards.

## The six

Each row is one solution ("car"), how much of it is fitted, what it is built
from, and its licence.

| # | Car | Fitted | Libraries and models | Licence |
|---|---|---|---|---|
| 1 | Rules on the table | nothing | NumPy, OpenCV | — |
| 2 | Network trained here from scratch | all, here | PyTorch, small convolutional net | — |
| 3 | Borrowed model as it downloads | nothing | Ultralytics YOLO26-seg | AGPL |
| 4 | Same model, fine-tuned here | all, here | Ultralytics YOLO26-seg | AGPL |
| 5 | Promptable foundation model, small fitted head | head only | SAM 2 via `transformers`, scikit-learn | permissive |
| 6 | Transformer segmenter, fine-tuned | all, here | RF-DETR-Seg | Apache 2.0 |

Three have a second way inside them:

- **2** — labels from the answer key, or from the arm's own movement.
- **5** — SAM 2 with a grid of points and a keeper, or SAM 3 with a word
  and no keeper.
- **6** — masks trained on visible pixels, or on the whole silhouette.

## One shared document, not a car

[Looking again at what was hidden](hidden-glasses.md): blind regions, pose
vetoes, learned ranker. The approach is unchanged. All six point at it.

## Block at the top of every document

- **What it uses** — libraries, and the model if there is one
- **What it does** — one paragraph
- **How the output is produced** — picture to list of glasses
- **How it differs from the other five** — one line each
- **What it costs** — labels, training, hardware, licence

## What the six let us compare

Each row is one question. The right column says which solutions to compare to
answer it.

| Question | Hold still, change one thing |
|---|---|
| Does a model beat rules? | 1 against the rest |
| Fit here, or borrow? | 2 against 3–6 |
| **What does training buy?** | **3 against 4 — same model, same library, same starting weights. Training also cuts the category list to one class, which cannot be had separately, so nothing varies that the training did not bring.** |
| Small head, or whole model? | 5 against 4 and 6 |
| Does architecture matter once trained? | 4 against 6 |
| Does predicting the hidden part help? | inside 6 |

## Scorecard: what to add

Place error saturates (see [the
examiner](the-examiner.md#how-far-out-was-the-place)). Two fine-tuned segmenters
already sat within half a millimetre of the exact-mask floor. So add:

- **mask overlap per glass** — share of the true silhouette captured
- **mask leak per glass** — share of the mask that is not that glass
- **both broken down by kind** — the stemmed kind is the hard one

The matcher already computes the overlap share, then throws it away. Recording
it is small work.

## Harder scenes, in order of cost

1. **More crowding** — more glasses, closer, bigger height differences.
   Cheapest. Already proven to spread the cars.
2. **A kind outside the borrowed vocabulary** — splits untrained from trained
   by construction.
3. **A handle** — only when orientation is wanted in the output. It inflates
   the shared width step for every car equally, so it adds common noise rather
   than separating them.

## Code: what goes, what stays

The table lists each code folder and the decision about it.

| Folder | Holds | Decision |
|---|---|---|
| `02-segment-glasses/bench` | the renderer, the scenes, the scorecard | keep, rename |
| `02-segment-glasses/01-rules-on-the-table` | **solution 1 as written** | keep |
| `02-segment-glasses/02-train-from-scratch` | **solution 2's network**, and the ranker | keep |
| `02-segment-glasses/results` | the two pipelines compared | keep |
| `02-segment-glasses/05-sam2-with-a-keeper` | shared pieces **and** two superseded models | split |

An audit cut this list down. Only one folder held anything dead.

**`02-segment-glasses/01-rules-on-the-table` is solution 1.** It groups points
where they stand on the table, not where they fall in the picture. That is
solution 1's method exactly.

**`02-segment-glasses/02-train-from-scratch` is solution 2.** Its network is the
one solution 2 describes, and `problem-5-learned` imports it.

**`02-segment-glasses/results` is cited from outside.** Problem 5's documents
point at its comparison in three places.

**Three problems use the examiner**: problems 2, 3 and 4. Deleting it would
change the input the six are compared on.

### Splitting `02-segment-glasses/05-sam2-with-a-keeper`

It held the shared pieces and two superseded models. The shared pieces belong in
the examiner. Only the models go.

| Move to the examiner | Why |
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

- When this plan was written, four of the six cars were not built. Documents
  were to say so and quote no number from a different model. All six are built
  now.
- Old measurements belong to SAM 1 and Mask R-CNN. They cannot be reused for the
  new cars. The exact-mask floor survives, because it measures the arithmetic,
  not a model.

## Diagrams: reuse, do not rewrite

The six writers asked for 79 pictures. 95 already existed, drawn for the old
solutions, and most showed ideas that survive. Each generator is over a thousand
lines long. So reuse beats writing 79 new ones.

The table says where each old generator's pictures go now.

| Existing generator | Where its pictures go now |
|---|---|
| cluster on the table | solution 1 |
| the network, and the voting | solution 2 |
| self-supervised from movement | solution 2, second way |
| segment anything | solution 5 |
| the fine-tuned segmenter | solutions 4 and 6 |
| amodal masks | solution 6, second way |
| move the camera, choosing the next look | the shared look-again document |
| split the blob | mostly stale; its splay and merge panels suit `problem.md` |

### Two kinds of rejection, and only one is a deletion

Many reused pictures were rejected. There are two reasons, and they lead to
different actions.

**Rejected on substance — delete.** The picture shows a side camera where the
survey looks from the top. Or it shows a method none of the six uses. Or it
argues against the problem statement. New labels cannot save these.

**Rejected on labels only — relabel and redraw.** The picture is right, but a
label is old. It says "SAM" where the document says SAM 2, or "solution 8" where
it is now solution 5. The generator still exists, so the fix is one line of
code. These are the valuable ones.

New pictures are needed only for new material:

- how a borrowed model builds a coarse outline, and its fixed category list;
- a transformer segmenter's queries, and set prediction against pruning;
- the untrained-against-trained pair, side by side;
- the ladder of how much is fitted, as one picture.

## Milestones

1. Plan, naming, deletion scope. **Check:** dependencies proven.
2. Rename docs and images. Fix every link. **Check:** links resolve, tests pass.
3. `problem.md` and `the-examiner.md`. **Check:** input and output stated once.
4. The six solution documents, by agents. **Check:** each against the code and
   against the other five.
5. `hidden-glasses.md`, `overview.md`, `README.md`, by hand. **Check:** the
   comparison table agrees with all six.
6. Diagrams: remap and renumber what exists, then draw only the gaps.
   **Check:** no document points at a picture that contradicts it.
7. Move the shared pieces into the examiner. **Check:** the floor still runs.
8. Delete the car code, rename the folders. **Check:** problem 5 still runs.

## How the documents get written

Six writer agents write one solution document each. Then four reviewer agents
each read documents they did not write. They check them against the code and
against each other.

Five documents are written by hand, because they must agree with all six:
`problem.md`, `the-examiner.md`, `hidden-glasses.md`, `overview.md`,
`README.md`.
