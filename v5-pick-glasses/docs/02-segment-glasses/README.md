# Problem 2 — segment the glasses

Several glasses stand on the table. The arm photographs them from the top and
has to work out **which pixels belong to which glass**, and where each glass
stands.

It stops there. It does not measure a shape, and it does not pick anything up.

This problem is answered **six different ways**, and that is the point of the
folder. Six methods, from a written rule to a fine-tuned transformer, are given
the same pictures and marked by the same examiner, so that they can be compared
and one of them chosen knowing what the choice costs. The cell they all share —
the layout, the two places the camera works from, the sensors and the vocabulary
— is described once in [the cell](../the-cell.md).

## Read in this order

1. [**The problem**](problem.md) — what is on the table, exactly what goes in
   and what must come out, the three difficulties, and what "done" means.
2. [**The test bench**](the-bench.md) — the arrangements, the pictures handed to
   every solution, the shared step that turns a mask into a place, and how a run
   is marked. **Every solution document assumes this one.**
3. [**Looking again at what was hidden**](hidden-glasses.md) — the part all six
   share, because a glass that appeared in no picture needs geometry rather than
   pixels.
4. [**The six solutions**](solutions/overview.md) — what they have in common,
   what each one changes, and which pair to compare first.

## The six

| # | Solution | Libraries and models | What is fitted |
|---|---|---|---|
| 1 | [Rules on the table](solutions/01-rules-on-the-table.md) | NumPy, OpenCV | nothing |
| 2 | [A network trained from scratch](solutions/02-train-from-scratch.md) | PyTorch, a small convolutional network | everything, here |
| 3 | [A borrowed model, as it downloads](solutions/03-yolo-zero-shot.md) | Ultralytics YOLO26-seg | nothing |
| 4 | [The same model, fine-tuned](solutions/04-yolo-fine-tuned.md) | Ultralytics YOLO26-seg | all of it, here |
| 5 | [A foundation model with a keeper](solutions/05-sam2-with-a-keeper.md) | SAM 2, scikit-learn | the keeper |
| 6 | [A transformer segmenter, fine-tuned](solutions/06-rf-detr-fine-tuned.md) | RF-DETR-Seg | all of it, here |

Each document opens with a block saying what it uses, how it produces the
output, how it differs from the other five, and what it costs — so the six can
be read side by side without reading any of them in full.

**Solutions 3 and 4 are the pair to look at first.** They are the same library,
the same model and the same downloaded weights, and one of them has had its
training continued on this cell's pictures. That training brings one other
change with it, which is that the borrowed list of everyday categories becomes a
single class — so nothing varies between the two that the training did not
bring, and the gap between them measures what training bought.

## What is built

The bench is built, including the shared arithmetic and the measurement of the
best answer any method could possibly give. **None of the six is built as a
solution on the bench**, and each document says so rather than describing code
that does not exist. One of them starts from something that exists: the network
solution 2 describes is already written in this project's code, and that
document separates what exists from what the design adds around it.

Building the yardstick before the cars is deliberate: a comparison whose
yardstick arrives after the results is one nobody can trust.
