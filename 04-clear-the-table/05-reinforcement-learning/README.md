# Solution 5 — reinforcement learning

This folder holds the solution that learns by trying. It is put in front of training tables,
it chooses pushes, and it is paid a score for what each push did. Nobody tells it which push
is right. By the end of this page you will know what this folder holds and how to train and
score the solution.

## How it learns

Each round of training sends several copies of the solution to clear training tables with
the current network. Their pushes and scores come back, and the network is changed so that pushes that
scored well become more likely. Because every push costs real physics time, it gets only a few
thousand pushes of experience, which is very little for this way of learning.

The full explanation, and what it scores, is on its page in the documents:
[reinforcement learning](../docs/solutions/05-reinforcement-learning.md).

## What is in this folder

| File | What it is |
|---|---|
| [`reinforcement_learning.py`](reinforcement_learning.py) | the network, the training by trying, and the solution that uses it |
| `weights/` | the trained networks; `reinforcement-v4.pt` is the one the results report |
| `results/` | how its pushes changed, round by round, during training |

## Running it

From the problem folder:

```
make reinforcement                            # train it by trying
make evaluate-reinforcement TABLES=50         # score it on the held-out tables
```
