# Step 5: lean it over in the air, and carry it out over the far legs

[← step 4](04-grip-lift-carry.md) · [index](README.md) · next: [step 6 →](06-feel-for-the-legs.md)

## What happens

1. **Lean.** The top turns 20° about its own gripped edge, which stays at
   `lean_at`. Its lower edge swings out towards the legs.
2. **Carry out.** Leaning, it goes in a straight line to 5 cm above where it
   will touch the far legs.
3. **Check** the fingertips still feel it.

**Joints that move:** most of them. The lean is a turn about a line along the
far row, which is not along wrist 1's axis, so it is not a three-joint move.

![a) the lean in the air, b) the carry out and the let-down](figures/tilt_side_view.png)

## What comes in

| From | Value | Seed 1 |
| --- | --- | --- |
| step 4 | the arm at the hanging pose | tool0 at (12.4, −43.3, 52.0) cm |
| step 3 | `plan.lean`: 4 poses | 5°, 10°, 15°, 20° |
| step 3 | `plan.out`: 14 poses | 2 cm apart, ending at `above` |
| step 3 | `plan.leaning` | 20° |

In `_put_on_legs()` in `task.py`:

```python
self._log.info(f"leaning the top {math.degrees(plan.leaning):.0f} degrees towards the arm, in the air")
self._arm.move_linear(plan.lean, speed=CARRY_SPEED)
self._log.info("carrying it out over the far legs")
self._arm.move_linear(plan.out, speed=CARRY_SPEED)
if not self._arm.in_contact:
    raise TaskFailed("the top slipped out of the fingers as it was leaned over")
```

---

## 5a. The lean

The 4 poses are `swing_about_edge(hanging, axis, 20°, 5°)`: the hanging pose
turned about **the gripped edge**, along the far row, by 5°, 10°, 15° and 20°.
This is the same turn as the whole-arm turn in the air, only 20° instead of 90°
([how the poses are made](../turn-by-whole-arm/07-turn-about-the-edge.md#7b-the-18-tool-poses)).

What it does:

- **The gripped edge stays put**, 45 cm out and 40 cm up.
- **tool0 moves on a 12 cm circle round it**, back towards the arm and a
  little down: seed 1 from (12.4, −43.3, 52.0) to (11.1, −39.4, 51.3) cm.
- **The top's lower edge swings out**, away from the arm, on a 16.5 cm circle.
- **The top now leans 20° towards the arm**: its "up" arrow, which pointed
  straight up, is now (−0.11, 0.32, 0.94), tipped 20° towards `toward`.

### Why lean here?

`lean_at` is 45 cm out: close enough in for the arm to hold the top hanging
there, and short of the near legs, which the top then passes over, leaning, on
its way out (the comment on `LEAN_RADIUS` in `task.py`).

### The grip, now

Leaning 20°, the top's weight starts to twist it in the fingers:

```
twist = m · g · d · sin 20° = 0.306 × 9.81 × 0.0555 × 0.34 = 0.06 N·m     (seed 1)
```

A third of what it would be held flat (0.17 N·m). That is the point of leaning
as little as possible.

---

## 5b. The carry out

The 14 poses are `straight_line(lean's last pose, above, 2 cm)`: evenly spaced
along the straight line, **all facing the same way**. The top keeps leaning
exactly 20° all the way.

| | tool0 | the top |
| --- | --- | --- |
| start | (11.1, −39.4, 51.3) cm | leaning 20°, 45 cm out |
| end, `above` | (18.1, −64.8, 48.9) cm | leaning 20°, its lower edge 5 cm above the hinge |

The line is 26.5 cm long. It goes out towards the legs and down 2.4 cm.

**Why a straight line spelled out as 14 poses, not just its two ends?**
`move_linear()` would draw a straight line between two poses anyway. But step 3
could only check the path if it had the poses: 2 cm apart, each followed from
the last. Handing MoveIt the same 14 poses means the arm follows exactly the
path that was checked.

Both moves are **checked for collisions**, the top included, and run at a tenth
of full speed. Neither has a fallback: if MoveIt cannot find at least 99% of the
path, the run stops. Step 3 already followed every one of these poses.

---

## 5c. Still holding?

```python
if not self._arm.in_contact:
    raise TaskFailed("the top slipped out of the fingers as it was leaned over")
```

The fingertip sensors must still feel the top.

**What this does not catch** is a top that has **sagged** in the fingers without
leaving the tip pads: turned a few degrees back towards hanging. The arm cannot
see that. It shows up in step 6 as the legs being felt higher, or not at all
([step 9](09-check-the-table.md#what-leaning-30-did)).

---

## What goes out

| Value | Seed 1 | Used in |
| --- | --- | --- |
| the arm at `above` | tool0 at (18.1, −64.8, 48.9) cm | step 6 |
| the top leaning 20°, its lower edge 5 cm above the hinge | – | step 6 |

## Fixed and measured numbers in this step

| Number | Value | Kind | Where |
| --- | --- | --- | --- |
| lean | 20° (or 30°) | choice | `task.py`, `LEANS` |
| lean step | 5° | choice | `task.py`, `SWING_STEP` |
| `ABOVE_LEGS` | 5 cm | choice | `task.py` |
| `LINE_STEP` | 2 cm | choice | `task.py` |
| `CARRY_SPEED` | 0.1 | choice | `task.py` |
| the poses | from step 3 | **worked out** | |

## What can go wrong

| Message | Why |
| --- | --- |
| `the top was not turned flat: straight-line move to [...] only solved N% of the way ...` | MoveIt could not follow the lean or the carry out |
| `the top slipped out of the fingers as it was leaned over` | the fingertips no longer feel it |

(The first message says "turned flat" because `main.py` uses the same words for
every job.)

## Where it is in the code

| What | Where |
| --- | --- |
| the two moves and the check | `task.py`: `_put_on_legs()` |
| the lean poses | `assembly/grasps.py`: `swing_about_edge()` |
| the carry-out poses | `assembly/grasps.py`: `straight_line()` |

[← step 4](04-grip-lift-carry.md) · [index](README.md) · next: [step 6 →](06-feel-for-the-legs.md)
