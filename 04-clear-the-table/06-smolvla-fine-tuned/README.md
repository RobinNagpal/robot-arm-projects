# Solution 6 — SmolVLA, fine-tuned

This folder holds the largest solution. SmolVLA is a vision-language-action model: it reads
pictures and a sentence, and it writes an action. It was made to move a small arm's joints, so
here a small correction is fitted to it, and it answers with a push for MoveIt instead. By the
end of this page you will know what this folder holds and how to fit and score it.

## What is fitted

The model's own weights never change. A small low-rank correction is added to it and trained,
so that from the two wrist pictures and the sentence it writes the numbers of a push. Its
examples are the arm's pushes that worked, with the pictures the camera took before each one,
so it shares imitation's weakness: it never sees a push that tipped a glass.

The full explanation, and what it scores, is on its page in the documents:
[SmolVLA, fine-tuned](../docs/solutions/06-smolvla-fine-tuned.md).

## What is in this folder

| File | What it is |
|---|---|
| [`smolvla_fine_tuned.py`](smolvla_fine_tuned.py) | the model, the fitting of its correction, and the solution that uses it |
| [`make_smolvla_training_data.py`](make_smolvla_training_data.py) | the pictures and answers it is fitted on |
| `weights/` | the fitted corrections, left out of git because they are large; `vla-r4` is the one the results report |
| `data/` | the pictures, also left out of git |

## Running it

From the problem folder:

```
make vla-data vla                             # make its pictures and fit the correction
make evaluate-vla TABLES=50                   # score it on the held-out tables
```
