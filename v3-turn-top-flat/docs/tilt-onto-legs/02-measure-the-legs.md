# Step 2: measure the legs, and check the top will fit

[← step 1](01-look-and-measure.md) · [index](README.md) · next: [step 3 →](03-plan-before-moving.md)

## What happens

1. Look at the four legs **close up**, from three views.
2. Work out **which two are far and which two are near**.
3. Work out **the hinge**: the line across the far legs' tops that the top's
   lower edge will rest on and turn about.
4. Check **the top will fit**: every leg must end up under it.

**Joints that move:** all six, to point the camera. Nothing is touched.

**Why now, before the top is picked up?** Later, the top hangs right over the
far legs and hides them from the wrist camera. So every measurement of the legs
is taken first, and the whole route is planned from it.

![From above: the top in its holders, the carry round to where it is leaned over, and the legs close up with the hinge, along and toward](figures/legs_from_above.png)

## What comes in

| From | Value | Seed 1 |
| --- | --- | --- |
| step 1 | four legs seen in the survey | – |
| step 1 | the floor, and the top's size | 0.0 cm; 24.4 × 16.5 × 1.9 cm |

---

## 2a. Three close views

`_measure_legs()` in `task.py`.

```
middle = the average of the four legs' centres, at floor height
toward = the level direction from the middle to the base
side   = (0, 0, 1) × toward                    square to it, level

view 1: camera 50 cm straight above the middle
view 2: camera 15 cm towards the arm from the middle, 45 cm up
view 3: camera 12 cm to the side of the middle, 45 cm up
each looking at the middle
```

The same `read_room()` as step 1 runs on these three pictures. Then:

- only legs that are **standing** count: taller than they are wide in both
  directions (`is_standing()`);
- there must be **exactly four**. If not: *"close up, N standing legs were found
  where the table goes, not 4"*.

The four replace the survey's legs in MoveIt's picture of the room.

---

## 2b. Which legs are which: `read_legs()`

`read_legs()` in `assembly/table.py` works it all out from the four boxes and
the base's position. Nothing about where the legs "should" be is looked up.

### Far and near

```
middle = the average of the four centres
out    = the level direction from the base to that middle, length 1

for each leg: how far out it is = leg centre · out       (a dot product)
the two furthest out are the far legs; the other two are the near legs
```

The dot product with `out` measures "how far along the line from the base".
Seed 1: the far two are 75.6 and 76.6 cm out along it, the near two 61.8 and 62.8.

### The directions

```
along  = far leg 2's centre − far leg 1's centre, made level and length 1
toward = near middle − far middle, with its part along `along` removed, made level and length 1
```

- **`along`** runs along the far row: the way the table's long side will run.
- **`toward`** runs from the far row to the near row, square to `along`. It
  points towards the arm.

"With its part along `along` removed" makes `toward` exactly square to `along`,
even if the legs stand a little crooked:

```
toward = toward − (toward · along) × along
```

Seed 1: along = (−0.948, −0.318, 0), toward = (−0.318, 0.948, 0).

### The hinge

```
far middle = the average of the two far legs' centres
offset     = the average, over all four legs, of (leg centre − far middle) · along
hinge      = far middle + along × offset,   at the height of the taller far leg's top
```

The offset moves the hinge to **halfway along the table**, the middle of all
four legs measured along the row. For four legs standing square it is 0.

The height is **the taller far leg's top**. The top rests on whichever far leg
is taller, and clears the other by the difference, a millimetre at most for legs
cut the same.

Seed 1: **hinge = (20.9, −73.2, 16.8) cm**, 76.1 cm from the base.

### Rows and thickness

```
rows      = (near middle − far middle) · toward       from the far row to the near row
thickness = the median of the legs' thicknesses
```

Seed 1: **rows = 13.8 cm**, thickness = 2.9 cm.

The log says:

```
  leg, 2.9 x 2.9 x 16.7 cm, at [0.299, -0.702]
  ... (one line per leg)
legs: the far two 76 cm out, their tops 16.8 cm up, the near two 13.8 cm in from them
```

---

## 2c. Will the top fit? `misfit()`

Tilted down about the hinge, the top will lie **from the hinge towards the arm,
its full width deep, centred along the far row**. Every leg must end up under it:

### The near legs must be under its near edge

```
reach = rows + thickness / 2          how far from the hinge the near legs' far-side faces are
reach must be ≤ width − 5 mm          (FIT_MARGIN)
```

Seed 1: 13.8 + 1.5 = **15.3 cm ≤ 16.5 − 0.5 = 16.0 cm** ✓

Otherwise it stops with a message like *"the near legs stand 16.1 cm from the
far ones' middles, and the top is only 15.5 cm wide"*.

### Every leg must be inside its ends

```
for each leg:
  sideways = |(leg centre − hinge) · along| + thickness / 2
  sideways must be ≤ length / 2 − 5 mm
```

Seed 1: 11.0 cm ≤ 12.2 − 0.5 = **11.7 cm** ✓ for all four.

Otherwise: *"a leg stands … cm out from the middle, past the end of the top"*.

**Why 5 mm margin?** Legs are measured to a couple of millimetres. A leg right
at the edge of the top might in fact be just past it.

If the top does not fit, the arm stops: *"the top will not go on these legs:
…"*. The top has not been touched.

---

## What goes out

| Value | Seed 1 | Used in |
| --- | --- | --- |
| the far legs, the near legs | – | step 3 (landing angle), MoveIt |
| `along` | (−0.948, −0.318, 0) | step 3 |
| `toward` | (−0.318, 0.948, 0) | steps 3, 9 |
| `hinge` | (20.9, −73.2, 16.8) cm | steps 3, 6, 7, 9 |
| `rows` | 13.8 cm | step 3 |

## Fixed and measured numbers in this step

| Number | Value | Kind | Where |
| --- | --- | --- | --- |
| close views | above at 50 cm; towards the arm 15 cm and 45 cm up; to the side 12 cm and 45 cm up | choice | `task.py`, `_measure_legs()` |
| legs needed | 4, standing | choice | `assembly/table.py`, `task.py` |
| `FIT_MARGIN` | 5 mm | choice | `assembly/table.py` |
| the legs, hinge, along, toward, rows | see above | **measured** | |

## What can go wrong

| Message | Why |
| --- | --- |
| `found N legs, and a table needs 4` | the survey saw fewer than 4 legs |
| `close up, N standing legs were found where the table goes, not 4` | one is lying down, or hidden, or an extra one is seen |
| `the top will not go on these legs: the near legs stand ...` | the top is not wide enough for the rows |
| `the top will not go on these legs: a leg stands ... past the end of the top` | the top is not long enough |

## Where it is in the code

| What | Where |
| --- | --- |
| the close views | `task.py`: `_measure_legs()` |
| far, near, along, toward, hinge, rows | `assembly/table.py`: `read_legs()`, `TableLegs` |
| will it fit | `assembly/table.py`: `misfit()` |
| standing | `perception/room.py`: `is_standing()` |

[← step 1](01-look-and-measure.md) · [index](README.md) · next: [step 3 →](03-plan-before-moving.md)
