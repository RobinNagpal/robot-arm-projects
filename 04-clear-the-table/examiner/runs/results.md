# Runs, table by table

This folder keeps every solution's answer to the same 25 held-out tables, one folder per table, so a table can be opened and the solutions compared on it. The results page adds up many more tables; this one shows what happened on each.

The 25 tables hold 98 glasses, and 38 of them are separated at the start. A glass is **separated** when the gripper could pick it: it is standing, inside the glass zone, and no neighbour is too close. 0 of the tables start with every glass separated; at most one in twenty may.

## What is in a table's folder

- `arrangement.json` and `arrangement.png`: where every glass starts, and how many are separated. A glass that is not separated lists the neighbours that crowd it.
- `<solution>_result.json` and `<solution>_result.png`: the same, after that solution has finished with the table, with how far each glass moved, whether it fell over and why the solution stopped. The push list gives every push it asked for, in order: the glass, the direction, the distance, the six settings handed to MoveIt, and whether the push was made, refused by MoveIt or rejected by the safety check. In the picture each push is a numbered arrow pointing the way the hand pushed. These files are made again by every run, so git does not keep them.

Positions are in millimetres from the arm's base. The glass zone, where a glass must stand to be picked, runs from 320 to 640 mm in x and from −440 to −80 mm in y. Each table is given the whole 15 arm minutes on its own.

Every solution is seeded by the table number, but MoveIt's planner draws its arm paths at random, so a second run can push a glass a little differently. Between two recordings, about one table result in fifty changed.

## All tables together

| Solution | Separated at start → end | Gain | Fell over | Tables better | Tables worse | Tables not touched | Pushes | Arm minutes |
|---|---|---|---|---|---|---|---|---|
| solution_1_geometry | 38 → 51 | +13 | 6 | 7 | 6 | 13 | 17 | 3.9 |
| solution_2_geometry_ranked | 38 → 45 | +7 | 6 | 4 | 6 | 15 | 11 | 2.7 |
| solution_3_imitation | 38 → 38 | +0 | 10 | 1 | 11 | 9 | 23 | 5.9 |
| solution_3_imitation_with_check | 38 → 38 | +0 | 0 | 0 | 0 | 23 | 3 | 2.3 |
| solution_4_world_model | 38 → 43 | +5 | 0 | 4 | 0 | 20 | 5 | 2.0 |
| solution_5_reinforcement | 38 → 40 | +2 | 2 | 1 | 2 | 19 | 29 | 9.8 |
| solution_5_reinforcement_with_check | 38 → 38 | +0 | 0 | 1 | 1 | 22 | 8 | 3.1 |
| solution_6_smolvla | 38 → 34 | -4 | 10 | 1 | 12 | 8 | 24 | 6.8 |
| solution_6_smolvla_with_check | 38 → 39 | +1 | 1 | 2 | 2 | 19 | 10 | 4.1 |
| ceiling | 38 → 47 | +9 | 0 | 5 | 0 | 20 | 5 | 0.7 |

A table is *worse* when it ends with fewer glasses separated or with a glass fallen over, and *not touched* when the solution stopped without a single push.

## Where the hand came down

A push's direction is measured against the direction straight away from the glass's nearest neighbour. Within 45° of it, the hand comes down **in the gap** between the two glasses; from 45° to 135° it comes down **at the side**; beyond that it comes down **on the far side** and pushes the glass towards its neighbour. Each cell is pushes made, out of pushes asked for; the rest were refused by MoveIt or rejected by the safety check. The ceiling's tries are not counted, only the pushes it made.

| Solution | In the gap | At the side | On the far side | Refused by MoveIt | Rejected by the check |
|---|---|---|---|---|---|
| solution_1_geometry | 0 of 0 | 17 of 30 | 0 of 0 | 13 | 0 |
| solution_2_geometry_ranked | 1 of 1 | 10 of 25 | 0 of 0 | 15 | 0 |
| solution_3_imitation | 0 of 4 | 10 of 21 | 13 of 15 | 17 | 0 |
| solution_3_imitation_with_check | 0 of 6 | 3 of 21 | 0 of 15 | 3 | 36 |
| solution_4_world_model | 0 of 1 | 5 of 6 | 0 of 0 | 2 | 0 |
| solution_5_reinforcement | 0 of 1 | 29 of 48 | 0 of 0 | 20 | 0 |
| solution_5_reinforcement_with_check | 0 of 1 | 8 of 33 | 0 of 0 | 4 | 22 |
| solution_6_smolvla | 3 of 11 | 14 of 20 | 7 of 10 | 17 | 0 |
| solution_6_smolvla_with_check | 1 of 11 | 7 of 18 | 2 of 10 | 6 | 23 |
| ceiling | 0 of 0 | 5 of 5 | 0 of 0 | 0 | 0 |

## Each table

Each cell is the number of separated glasses at the end, and ✗ marks a glass that fell over. The second column is the number at the start.

| Table | Start | 1_geometry | 2_geometry_ranked | 3_imitation | 3_imitation_with_check | 4_world_model | 5_reinforcement | 5_reinforcement_with_check | 6_smolvla | 6_smolvla_with_check | ceiling |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [10000](10000/arrangement.png) | 1 of 4 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 ✗ | 1 | 1 |
| [10001](10001/arrangement.png) | 2 of 4 | 4 | 4 | 2 | 2 | 2 | 2 | 0 | 1 | 1 | 4 |
| [10002](10002/arrangement.png) | 2 of 5 | 2 | 2 ✗ | 2 | 2 | 2 | 2 ✗ | 2 | 1 | 2 | 2 |
| [10003](10003/arrangement.png) | 1 of 3 | 3 | 1 | 1 ✗ | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| [10004](10004/arrangement.png) | 1 of 3 | 3 | 3 | 1 | 1 | 3 | 3 | 3 | 3 | 1 | 3 |
| [10005](10005/arrangement.png) | 1 of 3 | 1 | 1 | 1 ✗ | 1 | 1 | 1 | 1 | 0 ✗ | 1 | 1 |
| [10006](10006/arrangement.png) | 1 of 3 | 1 ✗ | 1 | 1 ✗ | 1 | 1 | 1 | 1 | 1 ✗ | 1 | 1 |
| [10007](10007/arrangement.png) | 2 of 4 | 4 | 2 | 2 | 2 | 3 | 2 | 2 | 2 | 2 | 4 |
| [10008](10008/arrangement.png) | 2 of 4 | 2 ✗ | 2 ✗ | 2 | 2 | 2 | 2 | 2 | 1 ✗ | 3 | 2 |
| [10009](10009/arrangement.png) | 2 of 4 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 1 ✗ | 2 | 2 |
| [10010](10010/arrangement.png) | 1 of 3 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 3 |
| [10011](10011/arrangement.png) | 2 of 5 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 1 ✗ | 2 | 2 |
| [10012](10012/arrangement.png) | 1 of 4 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| [10013](10013/arrangement.png) | 1 of 3 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 ✗ | 2 ✗ | 1 |
| [10014](10014/arrangement.png) | 2 of 5 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| [10015](10015/arrangement.png) | 1 of 4 | 2 ✗ | 1 ✗ | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 2 |
| [10016](10016/arrangement.png) | 2 of 4 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| [10017](10017/arrangement.png) | 1 of 3 | 1 ✗ | 1 | 1 ✗ | 1 | 1 | 1 ✗ | 1 | 1 ✗ | 1 | 1 |
| [10018](10018/arrangement.png) | 2 of 5 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 ✗ | 2 | 2 |
| [10019](10019/arrangement.png) | 1 of 4 | 3 | 1 ✗ | 2 ✗ | 1 | 1 | 1 | 1 | 1 ✗ | 1 | 1 |
| [10020](10020/arrangement.png) | 2 of 5 | 2 | 2 | 2 ✗ | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| [10021](10021/arrangement.png) | 2 of 4 | 2 | 2 | 2 ✗ | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| [10022](10022/arrangement.png) | 1 of 3 | 1 ✗ | 1 ✗ | 1 ✗ | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| [10023](10023/arrangement.png) | 2 of 5 | 2 | 2 | 2 ✗ | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| [10024](10024/arrangement.png) | 2 of 4 | 2 ✗ | 3 ✗ | 2 ✗ | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

## Making it again

`make runs` in the problem folder chooses the tables, runs every solution on them and writes this page.
