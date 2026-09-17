# Step 2: plan every pose before touching the top

[← step 1](01-look-and-measure.md) · [index](README.md) · next: [step 3 →](03-grip-the-edge.md)

Almost all of step 2 is **the same code as the wrist turn**, explained in full
in [the wrist docs, step 2](../turn-by-wrist/02-plan-before-moving.md). Only
**check 4**, "is the turn itself possible?", is different. This page recaps
the rest and explains check 4 for the whole-arm turn in full.

## What happens

**Nothing moves.** Every pose of steps 3 to 7 is worked out on the robot's
model and checked. If anything fails, the arm stops and says why, and the top
has not been touched.

## The parts that are the same

| Part | What it does | Seed 1 |
| --- | --- | --- |
| the turning spot | the middle of the gripped edge goes here | (50, 0, 40) cm |
| is it clear? | nothing seen within 40 cm of the spot | nearest leg 62 cm |
| wrist 1's axis at the spot | from a trial pose, nudging wrist 1 | (0.267, 0.964, 0) |
| the board's height | 2 × (edge z − centre z) | 16.5 cm |
| two grips | tool x along +along, or −along | tried A, then B |
| check 1 | can the arm get 8 cm above the edge? note the wrist side | tool0 36.6 cm |
| check 2 | can it reach the lifted pose, same wrist side? | tool0 49.1 cm |
| the hold | `H = P⁻¹ · pick` | tool 20.2 cm along the top's up |
| check 3 | can it hang the top at the spot, edge along the axis? | tool0 (50, 0, 52) cm |
| check 5 | work out the carry | 22 poses on an arc |

(Whether the turning spot needs the full 40 cm clear for this turn is a fair
question: this turn needs far less room. The check is shared by both turns and
sized for the wrist turn.)

---

## Check 4 for the whole-arm turn: can the arm follow the turn?

`_turn_blocked()` in `task.py`, the whole-arm branch:

```python
steps = swing_about_edge(
    hanging, hanging[:3, 0], flat_turn(hanging, hanging[:3, 0], BASE_POSITION), SWING_STEP
)
for number, pose in enumerate(steps):
    if not self._arm.can_reach(pose, wrist=wrist):
        turned = math.degrees(SWING_STEP) * number
        return f"the arm cannot follow the turn about the edge past {turned:.0f} degrees"
return None
```

Line by line:

### 1. The line to turn about

```
hanging[:3, 0]  =  column 0 of the hanging pose  =  the tool's x axis  =  the way the gripped edge runs
```

In the wrist turn, check 4 turned about **wrist 1's axis**. Here it turns
about **the edge itself**. Because the edge was lined up with wrist 1's axis,
the two lines point the same way. They are just in different places: the edge
is 40 cm up at the spot, and wrist 1 is higher and further back.

### 2. Which way

`flat_turn()` picks +90° or −90°, whichever leaves the tool reaching **away**
from the base. It is the same function the wrist turn uses
([wrist step 7a](../turn-by-wrist/07-turn-flat.md#7a-which-way-90-or-90)).
Seed 1: −90°.

### 3. The 18 poses

`swing_about_edge()` makes the tool pose at every 5° of the turn (`SWING_STEP`):
18 poses, from 5° to 90°. How they are made is in
[step 7](07-turn-about-the-edge.md#7b-the-18-tool-poses).

### 4. Can the arm reach each one?

`can_reach(pose, wrist=wrist)` solves for joint angles, with:

- the wrist flipped **the same way** as at the grip, since it cannot flip with
  the top in hand;
- the elbow bent the same way as the ready posture;
- no part of the arm hitting anything MoveIt knows about.

The first pose it cannot reach stops the check:

```
the top cannot be turned flat however it is gripped:
  the arm cannot follow the turn about the edge past 40 degrees
```

`number` counts from 0, so a failure at the first pose (5°) reads "past 0
degrees": the arm got nowhere.

### What this check does not cover

It is a good filter, but it is not a guarantee. Two gaps, and what covers
each:

| Not checked here | Why | What catches it |
| --- | --- | --- |
| **the top** hitting something | it is not in the fingers yet, so MoveIt does not know to carry it | step 7: MoveIt checks every point of the real path, with the top attached |
| **the path between poses** | each pose is solved **on its own**, from the ready posture, not one after another. Two poses can each be reachable, yet not one after the other without the arm changing shape | step 7: MoveIt follows the poses in order, each from the last, and reports how much of the path it managed |

Compare the wrist turn's check 4. There only one joint moves, so the path
between checked positions is known exactly, and 46 checks every 2° cover it
completely. That is one of the real differences between the two turns.

## What goes out

The same Route as the wrist turn: approach, pick, lifted, carry, wrist side.
The 18 turn poses are **not** kept. Step 7 makes them again from where the arm
really is.

## What can go wrong

The same as the wrist turn's step 2, except that check 4's messages are:

| Message | Why |
| --- | --- |
| `... the arm cannot hold it hanging at the turning spot` | no joint angles for the hanging pose |
| `... the arm cannot follow the turn about the edge past N degrees` | the pose at N + 5° cannot be reached |

## Where it is in the code

| What | Where |
| --- | --- |
| the whole plan | `task.py`: `_plan_route()` |
| check 4, both turns | `task.py`: `_turn_blocked()` |
| the 18 poses | `assembly/grasps.py`: `swing_about_edge()` |
| can the arm reach a pose | `arm/motion.py`: `can_reach()`, `_solve()` |

[← step 1](01-look-and-measure.md) · [index](README.md) · next: [step 3 →](03-grip-the-edge.md)
