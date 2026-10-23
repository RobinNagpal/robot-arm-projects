# Solution 4 — the world model

This folder holds the solution that learns what a push will do, and then searches for the best
push to make. It does not copy anyone. Instead it predicts, for a push it has not made yet,
where the glass will go and whether anything will tip, and it makes the push whose predicted
result is best. By the end of this page you will know what this folder holds, including the
safety check, and how to train and score it.

## What it learns from

It learns from every push the arm made, including the ones that tipped a glass and the ones
MoveIt could not plan. That is the difference from imitation: a model that has seen failures
can avoid them. Five copies of the network are trained, each on a different random sample of
the pushes. They agree where there is plenty of data and disagree where there is not, and the
search counts their disagreement against a push.

## The safety check

Because this model knows which pushes tip glasses, it can also judge another solution's push.
[`safety_check.py`](safety_check.py) wraps imitation, reinforcement learning or SmolVLA so that every
push they choose is shown to the world model first, and a push it expects to tip a glass is
not made. That is why the check lives here, beside the model it asks.

The full explanation is on two pages in the documents:
[the world model](../docs/solutions/04-world-model.md) and
[the safety check](../docs/solutions/safety-check.md).

## What is in this folder

| File | What it is |
|---|---|
| [`world_model.py`](world_model.py) | the five networks, their training, and the search that uses them |
| [`safety_check.py`](safety_check.py) | the safety check on another solution's push |
| `weights/` | the trained networks; `world-models-v3.pt` is the one the results report |

## Running it

From the problem folder:

```
make world-model                              # train it on the four rounds of pushes
make evaluate-world-model TABLES=50           # score it on the held-out tables
```
