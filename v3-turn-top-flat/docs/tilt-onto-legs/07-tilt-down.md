# Step 7: tilt it down onto the near legs

[← step 6](06-feel-for-the-legs.md) · [index](README.md) · next: [step 8 →](08-let-go-and-pull-out.md)

## What happens

The top rests its lower edge on the far legs, leaning 20° towards the arm. The
arm now **turns it about that resting edge**, towards itself, 3° at a time, until
it is **1.25° short of flat**, 3 mm above the near legs. The resting edge never
moves, so **nothing slides on the leg tops**.

The arm holds the top by its other edge, the gripped one. That edge moves on a
16.5 cm circle round the resting edge, coming down and in towards the arm, and
tool0, 12 cm further back, on a bigger one.

**Joints that move:** all six.

![c) the tilt down about the edge resting on the far legs](figures/tilt_side_view.png)

## What comes in

| From | Value | Seed 1 |
| --- | --- | --- |
| step 6 | the top resting on the far legs, the grip loosened | – |
| step 3 | `plan.resting_edge`, in the top's own frame | (0, −8.2, −1.0) cm |
| step 3 | `plan.axis` | along the far row, (−0.948, −0.318, 0) |
| step 3 | `plan.landing`, `plan.leaning` | 88.75°, 20° |
| step 4 | the hold `H` | – |

In `_put_on_legs()` in `task.py`:

```python
start = self._arm.tool_pose()
edge = board_point(start, held, plan.resting_edge)
steps = tilt_steps(start, edge, plan.axis, plan.landing - plan.leaning, TILT_STEP)
self._log.info(f"tilting it down about the far legs, {turn:.0f} degrees")
self._arm.start_recording()
self._arm.move_linear(steps, avoid_collisions=False, speed=CARRY_SPEED)
samples = self._arm.stop_recording()
```

---

## 7a. Where the resting edge really is

Step 3 planned the tilt about the **hinge**, where the legs were measured. But
step 6 found the legs by feel, a millimetre or two away. So the tilt is worked
out again from **where the arm really is now**:

```
start = tool_pose()                                     where the tool really is
edge  = board_point(start, H, resting edge)             = start · H⁻¹ · (0, −0.082, −0.010, 1)
```

`start · H⁻¹` is the top's pose. Multiplied by the resting edge, written in the
top's own frame, it gives that edge in the room: **where the top's edge is now
actually resting**.

## 7b. The tilt poses

```
steps = tilt_steps(start, edge, axis, 88.75° − 20°, 3°)
```

`tilt_steps()` in `assembly/grasps.py`:

```python
count = max(1, math.ceil(abs(angle) / step))          # ceil(68.75° / 3°) = 23
return [turned_about(tool_pose, point, axis, angle * k / count) for k in range(1, count + 1)]
```

23 poses, each the starting pose turned about the line through `edge` along
`axis`, by 68.75° × k / 23, **about 2.99° apart**.

`turned_about()` is the turn about a line that does not pass through the origin
([explained here](../turn-by-whole-arm/07-turn-about-the-edge.md#turning-a-pose-about-a-line-that-does-not-pass-through-0-0-0)):

```
M = [ R    edge − R · edge ]          p' = edge + R · (p − edge)
    [ 0          1         ]
```

The pivot is **the resting edge**, so it stays exactly where it is.

### Which way

The angle is **positive** about `axis = (0, 0, 1) × toward`. A positive turn
about that line tips the top's upper part **towards** `toward`: towards the arm,
down onto the near legs. (That was set up in step 3.)

### Where things go, seed 1

| | Start (leaning 20°) | End (1.25° short of flat) |
| --- | --- | --- |
| the resting edge | on the hinge, (20.9, −73.2, 16.8) cm | **the same** |
| the gripped edge | (19.4, −68.7, 32.6) cm | (15.7, −57.6, 18.1) cm |
| tool0 | (18.1, −64.8, 43.9) cm | (11.8, −46.2, 18.3) cm |
| the tool reaches | 20° from straight down | **almost level, away from the arm** |
| the top's centre | – | (18.3, −65.4) cm, 17.9 cm up |

The gripped edge, the top's near edge, ends just beyond the near legs, 18.1 cm
up: their tops (16.8 cm), plus half the top's thickness, plus the 3 mm left to
drop.

---

## 7c. Why turn about the resting edge, not the gripped one?

Because **turning about any other line makes the top slide on the legs**.

![Turning about the resting corner, nothing slides; turning about the gripped edge, the corner slides across the leg tops and drags the legs over](../figures/pivot_choice.png)

If the top turned about its gripped edge, the way the whole-arm turn does in the
air, its lower edge would swing on a circle and scrape across the leg tops.
Friction would drag the leg tops with it. A leg standing loose on the floor tips
over when a side push at its top, times its height, is more than its weight
(plus what presses on it) times half its thickness. The drag from a sliding board
is several times that ([the physics](../approaches/tilt-onto-legs.md#legs-falling-over-the-big-one)).

Turning about the exact edge that rests on the legs, that edge does not move at
all. The legs only feel weight pressing straight down, which steadies them.

**The tests check it.** `test_tilted_down_it_turns_on_that_edge_and_ends_on_all_four_legs`
in `test/test_table.py` checks, for 20 rooms, that the resting edge stays on the
hinge to within a nanometre at every tilt pose, that the top ends within 2° of
flat over all four legs, and just 3 mm above the near ones.

## 7d. Why the grip is loose

From step 6 the fingers are 4 mm wider than the top. The gripped edge lies on the
lower finger and turns between the two, like a hinge.

The top is now supported at **both** edges: by the legs, and by the arm. If the
fingers squeezed it, any error in the arm's path would be forced straight into
the legs, with nowhere to go. Loose, the top can rock a few degrees in the
fingers instead.

---

## 7e. The move

```python
self._arm.move_linear(steps, avoid_collisions=False, speed=CARRY_SPEED)
```

- **Straight lines between the 23 poses**, at a tenth of full speed.
- **Unchecked.** The top is resting on the legs, and MoveIt would count that as a
  collision and refuse. Every one of these poses was followed on the model, for
  the arm itself, in step 3.
- **At least 99% of the path** must come out, or the run stops.
- **Every joint reading is recorded**, for the report.

The log:

```
tilting it down about the far legs, 69 degrees
```

### After the move

```python
if not self._arm.in_contact:
    self._log.info("the fingertips no longer feel the top; the table check will say where it is")
```

With the grip loose, the top can lie on the lower finger's inner pad alone, away
from the fingertip sensors. So losing touch is **only logged**, not treated as a
slip. [Step 9](09-check-the-table.md)'s camera check decides whether it worked.

---

## 7f. What the joints did

Gazebo, seed 1, from leaning 20° to 3 mm above the near legs:

| Joint | 0.31 kg top: moved | 0.31 kg: peak N·m | 3.82 kg top: moved | 3.82 kg: peak N·m | Limit |
| --- | --- | --- | --- | --- | --- |
| base | 10.7° | 0.72 | 10.7° | 1.47 | 150 |
| shoulder | 33.3° | 42.54 | 33.0° | 67.46 | 150 |
| elbow | 51.5° | 26.73 | 52.0° | 46.78 | 150 |
| wrist 1 | 141.0° | 4.71 | 141.0° | 11.36 | 28 |
| wrist 2 | 20.6° | 0.88 | 20.6° | 2.15 | 28 |
| wrist 3 | 13.9° | 0.51 | 13.9° | 0.70 | 28 |
| how long | 8.6 s | | 8.6 s | | |

- **All six joints move.** The line the top turns about runs along the far row
  of legs. That is not along wrist 1's axis, the way the air turns line it up, so
  the base and wrists 2 and 3 have to join in
  ([why lining up saves joints](../turn-by-whole-arm/06-line-up-with-wrist-1.md#why-it-matters-for-the-whole-arm-turn)).
- **Wrist 1 turns 141°**, for the same reason as in the whole-arm turn: the
  shoulder and elbow tilt the forearm as they carry the wrist round, and wrist 1
  makes up for it ([why](../turn-by-whole-arm/07-what-each-joint-does.md#why-142-and-not-90)).
- **Well inside the limits**, even for a 3.8 kg top: wrist 1 at 11.4 of its
  28 N·m, the shoulder at 67 of its 150.
- **The same movement for both weights.** The path is the same; only the efforts
  grow.

**How long.** Wrist 1 turns furthest, 141°, and every joint's limit here is
18°/s: at least 7.8 s. With speeding up and slowing down, 8.6 s.

---

## What goes out

| Value | Seed 1 | Used in |
| --- | --- | --- |
| the arm at the last tilt pose, `placed` | tool0 at about (11.8, −46.2, 18.3) cm | step 8 |
| the top 1.25° short of flat, 3 mm above the near legs | – | step 8 |
| every joint reading during the tilt | about 8.6 s | step 9, the report |

## Fixed and measured numbers in this step

| Number | Value | Kind | Where |
| --- | --- | --- | --- |
| `TILT_STEP` | 3° | choice | `task.py` |
| `CARRY_SPEED` | 0.1 | choice | `task.py` |
| least of the path that must come out | 99% | choice | `arm/motion.py`, `move_linear()` |
| the resting edge's real place | – | **worked out** from where the arm is | |
| the tilt angle | 68.75° | **worked out** in step 3 | |

## What can go wrong

| Message | Why |
| --- | --- |
| `the top was not turned flat: straight-line move to [...] only solved N% of the way ...` | the arm could not follow the tilt |
| `the fingertips no longer feel the top; the table check will say where it is` | a log line only |

## Where it is in the code

| What | Where |
| --- | --- |
| the tilt | `task.py`: `_put_on_legs()` |
| the poses | `assembly/grasps.py`: `board_point()`, `tilt_steps()`, `turned_about()` |
| the test that nothing slides | `test/test_table.py` |

[← step 6](06-feel-for-the-legs.md) · [index](README.md) · next: [step 8 →](08-let-go-and-pull-out.md)
