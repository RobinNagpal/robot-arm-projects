# The safety check

The safety check is not a solution of its own. It lets the [world model](04-world-model.md)
look at another solution's push before MoveIt does. This page explains how it works and
what it can and cannot fix.

## How it works

Every push the solution chooses is first shown to the world model, which predicts the
chance that the push tips a glass if MoveIt plans it. If that chance is above 15 %, the push
is rejected. The glass is then set aside for this table, and the solution is asked again,
exactly as if MoveIt had refused the push. The 15 % limit was set on the training tables.

So the solution still chooses the glass, the direction and the settings. The check only
rejects pushes that look dangerous, and it never changes a push. A solution with the check
is a hybrid, because two models now take part in the decision.

## What it fixes and what it does not

| With the check | Glasses broken | Gain |
|---|---|---|
| 3 Imitation | 19 → 1 | +3 → +3 |
| 5 Reinforcement learning | 3 → 1 | +3 → +0 |
| 6 SmolVLA | 22 → 0 | −3 → −1 |

The check works like a filter on a function's outputs: it can remove bad values, but it
cannot produce values the function never gave. So it removes almost all breakage, but it
adds no gain, because these solutions rarely propose a push that frees a glass. The change
in reinforcement learning's gain is within its range, so it is not a real difference.

Two other ideas were tried on the training tables and did not help. Letting the world model
choose safer settings for a risky push did no better than rejecting it. Also rejecting
pushes the world model expected to leave fewer glasses with room changed nothing.
