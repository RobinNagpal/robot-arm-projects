# Step 8: hold it flat, check it, report

[← step 7](07-what-each-joint-does.md) · [index](README.md)

## What happens

1. Straight after the turn: **did the top stay in the fingers?**
2. **How flat is it**, as far as the arm can tell from its own joint angles?
3. **Hold it still for 5 seconds.**
4. **Is it still in the fingers?**
5. **Report** what every joint did, and whether it worked.

**Joints that move:** none.

![How flatness is worked out from the normal, and the order of the last checks](figures/flat_check.png)

## What comes in

| From | Value | Seed 1 |
| --- | --- | --- |
| step 1 | the top's box `P`, and its measured size | 24.4 × 16.5 × 1.9 cm |
| step 2 | `route.pick`, to work out the hold `H` | – |
| step 7 | every joint reading during the turn | about 7.9 s of them |
| step 7 | the arm, wrist 1 at −175.3° | – |

---

## 8a. Recording the joints

While the turn runs, and again while the top is held, every message on
`/joint_states` is kept (`start_recording()`, `stop_recording()`). Each
reading, a `JointSample`, holds:

| Field | Meaning |
| --- | --- |
| `time` | simulated seconds |
| `positions` | the six joint angles, rad |
| `efforts` | the six joint torques, N·m |
| `touching` | did the fingertips report a contact in the last 0.15 s? |

---

## 8b. Did it slip during the turn?

```python
if not self._arm.in_contact:
    result.slipped_at = self._turned_when_let_go(start, turn)
    return result
```

If the fingertip sensors no longer feel the top, **that is an answer, not a
crash**. How heavy a top the turn can take is one of the things being found
out. The arm works out **how far into the turn** it lost the top:

1. Find the last joint reading marked `touching`.
2. Forward kinematics gives the tool's pose at that reading.
3. Compare the tool's reach direction (its z axis) then with at the start of
   the turn:

   ```
   turned = arccos( start tool z · last-touching tool z )
   ```

   Both are unit directions, so their dot product is the cosine of the angle
   between them.

The report says *"the fingertips lost the top 82 degrees from hanging straight
down"* and the run counts as a failure. The sensors only say the top has gone
from the tip pads. It may have twisted down in the fingers, still pinched by
the inner pads, or it may have fallen. They cannot tell which.

---

## 8c. How flat, by the arm's own reckoning

```python
held  = hold(top, route.pick)                          # H, as in step 3
board = self._arm.tool_pose() @ np.linalg.inv(held)    # top = tool · H⁻¹
tilt  = math.acos(min(1.0, abs(float(board[2, 2]))))
```

Line by line:

1. **`H`**, the tool measured from the top, from the grip ([step 3](03-grip-the-edge.md#3e-the-hold-h-where-the-tool-sits-on-the-board)).
2. **`tool_pose()`** is where the tool **really** is now, from the joint
   angles. **`tool · H⁻¹`** is where the top is. This assumes the top has not
   moved in the fingers.
3. **`board[2, 2]`** is row 2, column 2: the **z part of the top's third axis**,
   its **normal**, the direction out of its face.

Flat means the face looks straight up or straight down, so the normal is
(0, 0, 1) or (0, 0, −1). Its z part is then ±1.

```
tilt = arccos( | z part of the normal | )
```

| The top | normal's z part | tilt |
| --- | --- | --- |
| flat | ±1.000 | arccos 1 = 0° |
| 1° off | 0.9998 | 1° |
| hanging, upright | 0 | arccos 0 = 90° |

`min(1.0, …)` guards against a rounding error making it 1.0000001, which
`arccos` would refuse.

Compare step 1's lean check. There the normal should be **level**, so its z
part should be 0 and the code uses **arcsin**. Here it should be **vertical**,
so its z part should be ±1 and the code uses **arccos**.

Seed 1:

```
the top is flat, as far as the arm can tell: 0.1 degrees off level
```

Gazebo, asked directly (something the robot never does), had it level to
within 0.005°.

"As far as the arm can tell" matters. The number comes from the joints and
`H`, not from looking. A top that had sagged a degree in the fingers would
still read 0.1°.

---

## 8d. Hold it still for 5 seconds

```python
self._arm.start_recording()
time.sleep(HOLD_FLAT)            # 5 s
holding = self._arm.stop_recording()
```

**Why wait?** A top slipping in the fingers does not always go at once. Flat,
its weight twists it in the pads with 0.17 N·m (seed 1), and a slow slip needs
time to show.

Then:

```python
result.held = self._arm.in_contact
```

The fingertips must still feel it.

---

## 8e. The report

`_joint_reports()` in `task.py` works out, for each joint:

| Column | How | Meaning |
| --- | --- | --- |
| **moved** | highest angle − lowest angle, during the turn | how far it travelled, whichever way |
| **net** | last angle − first angle, during the turn | where it ended compared with the start |
| **peak N·m** | the largest \|effort\| during the turn | the hardest it worked |
| **holding N·m** | the mean \|effort\| over the 5 s hold | what it takes to hold the top flat |

And how long the turn took (`_moving_time()`): from the first reading where
any joint moved by more than 0.0001 rad to the last.

`main.py` prints it. Seed 1, 400 kg/m³:

```
finished
  table top measured at 24.4 x 16.5 x 1.9 cm
  the turn by the wrist took 7.7 s
  joint                   moved      net  peak N·m  holding N·m
  shoulder_pan_joint       0.0°    +0.0°      0.33         0.00
  shoulder_lift_joint      0.0°    +0.0°     26.77        24.93
  elbow_joint              0.0°    +0.0°     27.25        25.88
  wrist_1_joint           90.0°   -90.0°      4.07         2.71
  wrist_2_joint            0.0°    +0.0°      0.04         0.00
  wrist_3_joint            0.0°    +0.0°      0.04         0.04
  the arm puts the top 0.1 degrees off level
  held flat for 5 s, and the fingers still feel the top
```

(The exact layout of the lines is from `_report()` in `main.py`. The numbers
are from [`../../turn-results.md`](../turn-results.md).)

What it shows:

- **Only wrist 1 moved.** Every other joint: 0.0°.
- **The shoulder and elbow work hardest** while not moving at all. They hold up
  the whole forearm, wrist, gripper and top. That is under a fifth of their
  150 N·m.
- **Wrist 1** peaked at 4.07 N·m, 15% of its 28 N·m.
- **The base, wrists 2 and 3** feel almost nothing. Gravity twists about level
  lines, and their axes point other ways.

### Success or failure

The run **succeeds** (exit status 0) only if:

1. the fingertips did not lose the top during the turn, **and**
2. they still feel it after the 5 s hold.

Otherwise it logs why and exits with status 1:

| Message | Why |
| --- | --- |
| `the fingertips lost the top ... degrees from hanging straight down` | 8b |
| `it has twisted in the fingers or fallen out: the sensors cannot tell which` | the line after it |
| `the fingers lost the top in the 5 s it was held flat` | 8d |
| `no joint readings came in during the turn` | nothing was recorded |

The top is left held flat in the fingers. This job ends there.

---

## Fixed and measured numbers in this step

| Number | Value | Kind | Where |
| --- | --- | --- | --- |
| `HOLD_FLAT` | 5 s | choice | `task.py` |
| a reading counts as touching within | 0.15 s | choice | `arm/motion.py`, `SAMPLE_CONTACT_FRESHNESS` |
| contact now, within | 0.4 s | choice | `arm/motion.py`, `CONTACT_FRESHNESS` |
| a joint counts as moving above | 0.0001 rad per reading | choice | `task.py`, `_moving_time()` |
| tilt, efforts, times | see above | **measured** | |

## Where it is in the code

| What | Where |
| --- | --- |
| the checks, in order | `task.py`: `run()` |
| where it slipped | `task.py`: `_turned_when_let_go()` |
| recording joints, contact | `arm/motion.py`: `start_recording()`, `stop_recording()`, `in_contact` |
| per-joint numbers, duration | `task.py`: `_joint_reports()`, `_moving_time()` |
| the printed report, exit status | `main.py`: `main()`, `_report()` |

[← step 7](07-what-each-joint-does.md) · [index](README.md)
