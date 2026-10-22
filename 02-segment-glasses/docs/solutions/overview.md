# The six solutions — one question, six ways to see

## Introduction

[Problem 2](../problem.md) asks for one record per glass: its pixels and its
place on the table. Six methods answer it. The point is not to find the one
answer. The point is to compare them, and to choose one knowing what it costs.

This page is a map of the six, in three tables: what each is built from, how
each works, and what each scored. Read it first, then any solution that
interests you.

## What all six share

All six get the same pictures and the same marking from [the
examiner](../the-examiner.md). Read that page before any solution.

**Every solution contributes only the masks.** The examiner turns each mask into
a place and a width, the same way for all six. So a difference in score is a
difference in the masks.

## What each one is built from

Each row says what you must install, train and accept the licence of to run that
solution. The rows go from nothing fitted at the top to everything fitted at the
bottom.

| Solution | What it is built from |
|---|---|
| **1. [Rules on the table](01-rules-on-the-table.md)** | NumPy and OpenCV, both already in the cell. Nothing is fitted: no model, no training set, no weights. No licence condition. |
| **2. [A network trained from scratch](02-train-from-scratch.md)** | PyTorch and a small convolutional network written for this project. All of it is fitted on this cell's pictures, so it needs a training set and a training run. No licence condition. |
| **3. [A borrowed model, as it downloads](03-yolo-zero-shot.md)** | Ultralytics YOLO26-seg, used exactly as it downloads. Nothing is fitted. Licensed under AGPL-3.0. |
| **4. [The same model, fine-tuned](04-yolo-fine-tuned.md)** | The same model and weights as solution 3, trained further on this cell's pictures. Needs a labelled training set and a training run. The same AGPL-3.0. |
| **5. [A foundation model with a keeper](05-sam2-with-a-keeper.md)** | SAM 2 through the `transformers` library, plus a small scikit-learn classifier on top. Only the classifier is fitted. Permissive licence. |
| **6. [A transformer segmenter, fine-tuned](06-rf-detr-fine-tuned.md)** | RF-DETR-Seg, a transformer segmenter, all fitted on this cell's pictures. Needs a labelled training set, a training run and the biggest machine of the six. Apache 2.0, a permissive licence. |

## How each one works

The same six, now by what happens when a picture arrives. Each row answers one
question: where does the knowledge about glasses come from?

| Solution | How it works |
|---|---|
| **1. Rules on the table** | Each pixel with a depth reading becomes a point in the room. The height is dropped, so each glass becomes a flat patch of dots on the table. Dots close together are one glass. A circle is fitted to each group. A group too wide for the kind is cut in two. The knowledge is a rule somebody wrote. |
| **2. A network trained from scratch** | A small network learns, for each pixel, whether it is glass and which way the middle of its glass lies. Each glass pixel votes for a point on the table. A pile of votes is a glass. The knowledge comes only from this cell's training half. |
| **3. A borrowed model, as it downloads** | A model trained on photos of everyday objects looks at this cell's pictures. It returns a box, a name, a confidence and an outline per object. Outlines named as drinking vessels are kept as masks. The knowledge is entirely somebody else's. |
| **4. The same model, fine-tuned** | The same model as solution 3, trained further on this cell's pictures, with its category list cut to one class. It returns one outline per glass, with no name to filter. The knowledge starts borrowed and moves towards this cell. |
| **5. A foundation model with a keeper** | A large model that can outline anything is prompted with a grid of points. It returns many outlines. Each is turned into a few table measurements, such as footprint width. A small classifier reads them and says keep, drop, or more than one glass. Only the keeper is fitted. |
| **6. A transformer segmenter, fine-tuned** | A transformer predicts a fixed number of candidate objects at once, each with an outline. Training on this cell's pictures teaches it which candidates are glasses. The knowledge starts borrowed, like solution 4, but the model has a different shape. |

## What each one scored

Each solution was run on spaced and on crowded arrangements, as [the
examiner](../the-examiner.md#every-solution-is-tested-twice-once-on-each-family)
describes. Each run was repeated over five blocks of 20 arrangements. The table
gives the average, with the lowest and highest block in brackets. Where two
brackets overlap, the test has not separated those two solutions. The full
tables, and what they mean, are on the [results
page](../../results/README.md).

Read the crowded column against 86.4, not 100. That is what the examiner's own
perfect masks reach.

| Solution | Spaced, found per 100 | Crowded, found per 100 | Why those two results |
|---|---|---|---|
| **1. [Rules on the table](01-rules-on-the-table.md)** | **100.0** (100.0–100.0) | 73.0 (70.3–75.5) | The rule needs bare table between two glasses. Normal spacing always leaves some, so it finds every glass. Crowding removes it, and two glasses join into one group. |
| **2. [A network trained from scratch](02-train-from-scratch.md)** | 64.1 (62.4–66.7) | 74.6 (71.3–79.8) | A glass whose middle is outside the picture casts votes that land nowhere. That is a limit of the voting design, not of training. Crowding does not make it worse. It has the widest spread here. |
| **3. [A borrowed model, as it downloads](03-yolo-zero-shot.md)** | 6.4 (2.0–11.9) | 2.1 (0.0–4.2) | It has never seen pictures like these. It mostly sees nothing, and calls what it finds a sports ball or a frisbee. On one crowded block it found no glass at all. |
| **4. [The same model, fine-tuned](04-yolo-fine-tuned.md)** | **99.4** (99.0–100.0) | 72.0 (70.8–72.9) | Training fixed the gap between its old pictures and these, so it finds almost everything. A glass partly behind another still comes back as a slice, which costs it on crowded tables. |
| **5. [A foundation model with a keeper](05-sam2-with-a-keeper.md)** | 83.0 (78.0–86.1) | 73.6 (71.9–76.6) | The keeper only chooses among the borrowed model's shapes. So it never invents or merges a glass. It also never finds a glass the borrowed model missed, which is where its missing one in six goes. |
| **6. [A transformer segmenter, fine-tuned](06-rf-detr-fine-tuned.md)** | 96.4 (94.9–98.0) | **81.9** (77.2–86.5) | Two touching outlines get two query slots, so there is never a joined region to cut apart. That helps most on crowded tables, where it is the only one clear of the group. |

Three findings matter most. The [results
page](../../results/README.md#what-the-comparison-says)
explains each one.

- **Four of the six are not separated on crowded tables.** Solutions 1, 2, 4
  and 5 have overlapping brackets.
- **Solution 3 against solution 4 measures what training bought**: 6.4 against
  99.4. The cause is the **domain gap**, the difference between the pictures a
  model learned from and the pictures it is shown. [Solution
  3](03-yolo-zero-shot.md#the-domain-gap-which-is-the-main-risk) explains it.
- **The two mask numbers disagree about who is best.** Solution 4 covers the most
  glass but also claims the most table.

One cost is not in the scores. Solutions 3 and 4 are AGPL-3.0. That costs
nothing here, because nothing ships. But they would need replacing if this work
ever shipped. [Solution 3](03-yolo-zero-shot.md#the-licence-which-is-the-real-cost-here)
explains why.

All six are built and have been run by the examiner. Where something could not
be run, its document says so. No number here is an estimate.

## Where to go next

- [The examiner](../the-examiner.md): the shared input, output and marking.
  **Read this before any solution document.**
- [The problem](../problem.md): what is asked for, and the difficulties.
- [Looking again at what was hidden](../hidden-glasses.md): the part all six
  share, which finds a glass no picture held.
- Then the six, in order: [1](01-rules-on-the-table.md),
  [2](02-train-from-scratch.md), [3](03-yolo-zero-shot.md),
  [4](04-yolo-fine-tuned.md), [5](05-sam2-with-a-keeper.md),
  [6](06-rf-detr-fine-tuned.md).
