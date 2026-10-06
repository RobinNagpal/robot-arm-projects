# The six solutions — one question, six ways to see

## Introduction

Problem 2 asks for one record per glass: which pixels are that glass, and where
it stands on the table. This folder answers that question six times over, with
six quite different methods, and the point of having six is **not** that one of
them is the answer. The point is to be able to compare them, and then to choose
one knowing what the choice costs.

This document is the map of all six, and it is three tables. The first says
**what each one is built from**, which is the model, the library and the
licence. The second says **how each one works**, in a few sentences each. The
third says **what each one scored**, and the prose after it explains the two
results that are worth more than the rest. Read this document first, then the
document for any solution that interests you.

## What all six share

All six are asked the same question, shown the same arrangements of glasses and
marked the same way, which is what lets a gap between two scores be read as a
statement about the method. [The examiner](../the-examiner.md) describes that
arrangement in full and is the document to read before any solution document.

The one part of it worth repeating here is the part the tables below rest on.
**Every solution contributes only the masks**, because turning a mask into a
place and a width belongs to the examiner and is done the same way for all six.
So a difference in a score is a difference in the masks, and nothing else.

## What each one is built from

This is the shopping list. Read the right column as what you would have to
install, train and accept the licence of in order to run that solution, and the
order of the rows as how much is fitted, from nothing fitted at the top to
everything fitted at the bottom.

| Solution | What it is built from |
|---|---|
| **1. [Rules on the table](01-rules-on-the-table.md)** | NumPy and OpenCV, both already in the cell. Nothing is fitted, so there is no model, no training set and no weights file. No licence condition of any kind. |
| **2. [A network trained from scratch](02-train-from-scratch.md)** | PyTorch and a small convolutional network written for this project. Everything in it is fitted, on this cell's own pictures, so it needs a training set and a training run. No licence condition. |
| **3. [A borrowed model, as it downloads](03-yolo-zero-shot.md)** | Ultralytics YOLO26-seg, used exactly as it downloads. Nothing is fitted here, so there is no training set and no training run. Licensed under AGPL-3.0, whose network clause reaches a product that only ever serves answers. |
| **4. [The same model, fine-tuned](04-yolo-fine-tuned.md)** | The same Ultralytics YOLO26-seg and the same downloaded weights as solution 3, with training continued on this cell's pictures. Needs a labelled training set and a training run. The same AGPL-3.0. |
| **5. [A foundation model with a keeper](05-sam2-with-a-keeper.md)** | SAM 2 through the `transformers` library, with a small classifier from scikit-learn fitted on top of it. Only that classifier is fitted; the big model is never touched. Permissively licensed. |
| **6. [A transformer segmenter, fine-tuned](06-rf-detr-fine-tuned.md)** | RF-DETR-Seg, a transformer segmenter, with all of it fitted on this cell's pictures. Needs a labelled training set, a training run and the most machine of the six. Apache 2.0, which is permissive. |

## How each one works

The same six in the same order, now by what actually happens when a picture
arrives. Each one is a different answer to the single question of where the
knowledge about glasses comes from.

| Solution | How it works |
|---|---|
| **1. Rules on the table** | It stops asking about the picture and asks about the room. Every pixel with a depth reading becomes a point standing in the room, the height is thrown away so each glass becomes a flat patch of dots on the table, and dots within one chosen distance of each other are taken to be one glass. A circle is then fitted to each group, and a group too wide for the kind on the table is two glasses and gets cut in two. The knowledge is a sentence somebody wrote down. |
| **2. A network trained from scratch** | A small network is trained on this cell's own pictures to say, for each pixel, whether it is glass and which direction the middle of its glass lies in. Every glass pixel then votes for a point on the table, the votes pile up, and a pile of votes is a glass. Nothing is borrowed, so the knowledge comes entirely from this cell's training half. |
| **3. A borrowed model, as it downloads** | A model somebody else trained on photographs of everyday objects is pointed at this cell's pictures and asked what it can see. It returns a box, a name, a confidence number and an outline per object. The outlines named as drinking vessels are kept, the names are then thrown away, and the kept outlines are the masks. The knowledge is entirely somebody else's and nothing here adjusts it. |
| **4. The same model, fine-tuned** | The same model and the same downloaded weights as solution 3, with its training continued on this cell's pictures and its list of everyday categories cut to a single class. It then returns one outline per glass directly, with no name to filter on and nothing to throw away. The knowledge starts as somebody else's and is moved towards this cell. |
| **5. A foundation model with a keeper** | A large model that segments anything is prompted with a grid of points, and it returns a great many outlines of whatever happens to be under them. Each outline is then turned into a few measurements on the table, such as the width of its footprint, and a small classifier fitted on this cell's training half reads those numbers and answers one of three things: keep it, drop it, or this is more than one glass. The borrowed knowledge is left untouched, and only the keeper is fitted. |
| **6. A transformer segmenter, fine-tuned** | A transformer is given the picture and predicts a fixed number of candidate objects at once, each with its own outline, rather than scoring regions one at a time. Training on this cell's pictures teaches it which candidates are glasses and what their outlines should be. The knowledge starts borrowed, like solution 4, but the shape of the model is different. |

## What each one scored

Every solution was run by the examiner on the same two sets of held-out
arrangements: 100 glasses spaced as the cell's own layout rule gives them, and
101 glasses crowded closer than that rule allows. Read the right column as how
many of those glasses the method found, and then how good its masks were. The
full numbers with every column are in
[`02-segment-glasses/results/`](../../../02-segment-glasses/results/).

For scale, no method could find all 101 crowded glasses, because a glass
standing wholly behind another appears in no picture at all. The examiner's own
perfect masks find 83 of them, so 83 is the mark to read the crowded numbers
against.

| Solution | What it scored |
|---|---|
| **1. Rules on the table** | Found every one of the 100 spaced glasses, which no other solution did, and at the middle glass its masks claimed no pixel that was not glass. Crowded, it found 71 of the 83 available and handed over 10 reports that each covered two glasses, because the strip of bare table its one rule depends on is sometimes not there. |
| **2. A network trained from scratch** | Found 63 of 100 spaced and 72 of 101 crowded. The misses are a limit of its voting design rather than of its training: a glass whose middle falls outside the picture casts votes that land nowhere. Where it did find a glass its place was the most accurate of the six on the spaced set, half a millimetre out at the middle glass. |
| **3. A borrowed model, as it downloads** | Found 10 of 100 spaced and 4 of 101 crowded, the worst score of the six by a wide margin. It is not confused about glasses; it is being shown a kind of picture it has never seen, and it names what it does find a sports ball or a frisbee. **This is the result it was built to produce.** |
| **4. The same model, fine-tuned** | Found 99 of 100 spaced and 73 of 101 crowded. Of the methods that found most of the glasses it drew the most complete masks, covering 99.8 per cent of the glass spaced and 99.3 per cent crowded. Its masks do claim a thin margin of table around each glass, about four per cent, because a learned outline follows the shape coarsely and its edge sits a little outside the glass. |
| **5. A foundation model with a keeper** | Found 81 of 100 spaced and 73 of 101 crowded, with nothing merged, split or falsely reported in either set, and its masks never claimed a pixel that was not glass. It is the cleanest of the learned solutions and not the most complete: it covered 96.8 per cent of the glass on the spaced set, against solution 4's 99.8. |
| **6. A transformer segmenter, fine-tuned** | Found 96 of 100 spaced and 78 of 101 crowded, which is the closest any method came to the 83 a perfect mask finds. Its masks claimed no pixel that was not glass. It is the best of the six on crowded tables and it costs the most machine to train. |

Two results in that table are worth more than the others.

**The first is solution 3 against solution 4, and it is the sharpest comparison
in the set.** Same library, same model, same downloaded weights, same examiner.
The training also replaces the borrowed list of everyday categories with a
single class, which cannot be had separately from the training itself, so
nothing varies between the two that the training did not bring. The gap is 10
glasses found against 99, and that gap is a measurement of what fine-tuning
bought.

The reason it is so large has a name. The **domain gap** is the difference
between the pictures a model was fitted on and the pictures it is asked about.
Solutions 1 and 2 have none, because one is a rule and the other learned from
this cell's own pictures. Solutions 3, 4, 5 and 6 all start from weights fitted
on photographs of the everyday world, while this cell renders a grey picture
shaded from depth readings. A model fails across such a gap in a particular way:
not by producing nonsense, but by producing confident, plausible, wrong answers,
which is worse because nothing afterwards looks suspicious. Fine-tuning is the
standard repair, which is why solutions 4 and 6 exist at all.

**The second is that the two mask numbers disagree about who is best.** Solution
4 drew the most complete masks and also claimed the most table that was not
glass; solutions 1, 5 and 6 claimed no table at all and covered less of the
glass. Neither habit shows up in the places the methods report, because the step
that turns a mask into a place is deliberately forgiving. That is exactly why
the examiner measures the mask itself, and it is the reason "which one is best"
has no single answer here.

One cost does not appear in any of the three tables. Solutions 3 and 4 are
AGPL-3.0, whose network clause reaches a product that never ships a copy of the
model and only ever serves answers from it, while everything else this project
depends on is permissively licensed. That costs nothing here, because this
folder compares methods and ships nothing. It is worth knowing anyway: the two
solutions that win on convenience are the two that would need replacing if the
work ever shipped.

All six are built, and all six have been run by the examiner. Where something
could not be run, the result is absent and the reason is written down in the
document that asks for it, because no number in this project is an estimate.

## Where to go next

- [The examiner](../the-examiner.md) — the shared input, output and marking.
  **Read this before any solution document.**
- [The problem](../problem.md) — what is asked for, and the difficulties.
- [Looking again at what was hidden](../hidden-glasses.md) — the part all six
  share, which recovers a glass no picture held.
- Then the six, in order: [1](01-rules-on-the-table.md),
  [2](02-train-from-scratch.md), [3](03-yolo-zero-shot.md),
  [4](04-yolo-fine-tuned.md), [5](05-sam2-with-a-keeper.md),
  [6](06-rf-detr-fine-tuned.md).
