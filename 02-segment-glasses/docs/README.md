# Problem 2 — segment the glasses

Several glasses stand on the table. The arm photographs them from above. It must
say which pixels belong to which glass, and where each glass stands.
[The problem](problem.md) states this in full.

Six methods answer the same question. One examiner marks them all the same way,
so they can be compared. The arm, camera and glasses they share are described in
[the cell](../../01-rack-one-glass/docs/the-cell.md).

## Read in this order

1. [**The problem**](problem.md): what goes in, what must come out, and why it
   is hard.
2. [**The examiner**](the-examiner.md): the test arrangements, the pictures, the
   shared last step and the marking. Every solution document assumes it.
3. [**Looking again at what was hidden**](hidden-glasses.md): the step all six
   share for a glass that no picture showed.
4. [**The six solutions**](solutions/overview.md): a map of the six and their
   scores.

## The six

Each row names one solution, the libraries it uses, and how much of it is
fitted on this cell's pictures.

| # | Solution | Libraries and models | What is fitted |
|---|---|---|---|
| 1 | [Rules on the table](solutions/01-rules-on-the-table.md) | NumPy, OpenCV | nothing |
| 2 | [A network trained from scratch](solutions/02-train-from-scratch.md) | PyTorch, a small convolutional network | everything, here |
| 3 | [A borrowed model, as it downloads](solutions/03-yolo-zero-shot.md) | Ultralytics YOLO26-seg | nothing |
| 4 | [The same model, fine-tuned](solutions/04-yolo-fine-tuned.md) | Ultralytics YOLO26-seg | all of it, here |
| 5 | [A foundation model with a keeper](solutions/05-sam2-with-a-keeper.md) | SAM 2, scikit-learn | the keeper |
| 6 | [A transformer segmenter, fine-tuned](solutions/06-rf-detr-fine-tuned.md) | RF-DETR-Seg | all of it, here |

Each document opens with a short block. It says what the solution uses, how it
works, how it differs from the other five, and what it costs.

**Compare solutions 3 and 4 first.** They are the same model with the same
starting weights. Only solution 4 was trained on this cell's pictures. The
[results page](../results/README.md) explains what that gap
measures.

## The plan behind the six

[The plan](solutions-plan.md) lists the decisions in short form: what all six
share, why these six, and what was left for later.

## What is built

The examiner is built. All six solutions are built and have been run by it. The
scores of all six are on the [results
page](../results/README.md).

The examiner was built before the solutions on purpose. A test written after the
results are known is hard to trust.
