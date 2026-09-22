# Step 6 — turning it over and standing it down

The glass is held, weighed and squeezed correctly. What remains is to turn it
through 180 degrees and stand it mouth-down in a rack slot without touching
anything on the way.

Code: `rotate_tool()` and `descend_until_contact()` in `arm/motion.py`,
`rack/layout.py`, and `_invert_and_place()` in `task.py`.

## Turning about the grip, not about the wrist

Inverting a glass is a rotation. *What it rotates about* decides whether it is
safe.

The obvious implementation turns the tool about its own origin, because that is
what a pose command does. The fingertips are 170 mm from the tool origin, so
the glass swings through an arc 340 mm across — straight through whatever is
standing next to it.

Rotating about the **grip point** turns the glass on the spot, because the grip
point is the one place on the glass that is not moving relative to the fingers.

So `rotate_tool()` takes the point to turn about:

```python
turn = rotation_about(rotation[:, axis], angle)
moved = turn @ rotation
landing = about + turn @ (position - about)
```

and `task.py` passes the grip point, recomputed live from where the tool is now:

```python
def _grip_point(self):
    position, rotation = self._arm.current_pose()
    return position + rotation[:, 2] * FINGERTIP_OFFSET
```

`tilt()` and `turn_over()` are the same function with the two angles the task
uses — 20 degrees for the slip test, 180 for the real thing.

## The wrist limit, and why it is checked before the fingers close

The last wrist joint on a UR5e does not turn indefinitely. It stops a little
short, and there is a hard limit in the middle of its range that no plan can
cross.

That means whether the arm can invert a glass **depends on which way round it
took hold of it**. Approach from one side and the 180 degrees fits; approach
from the other and the wrist runs out halfway.

A parallel gripper is symmetric, so there are always exactly two ways round
that grip the same glass identically:

```python
for rotation in grasp_options(_grasp_rotation(approach)):
    hover above the glass in that orientation
    if self._arm.can_rotate_tool(math.pi):
        return rotation
```

`can_rotate_tool()` plans the turn without executing it. The arm asks this
question while hovering, **before the fingers close**, and takes the second way
round if the first cannot be turned.

Getting this wrong is the most expensive mistake available in the whole task,
because it is discovered with the glass already in the gripper and there is
nothing left to do but put it back down. It is also the kind of mistake that
works fine in testing and fails on the glass that happens to be standing at an
awkward angle.

## How much room a glass has in a slot

A glass going into a slot has `(spacing - width) / 2` of clearance on each
side. It pivots about its rim as it goes down, so the lean that uses up that
clearance is

    atan(clearance / height)

![How much a glass may lean going into a slot](../images/tilt-budget.png)

The numbers are less forgiving than they look. Slots are 100 mm apart:

| Glass | Clearance each side | Budget |
| --- | --- | --- |
| 80 mm wide, 90 mm tall | 10 mm | 6.3° |
| 80 mm wide, 175 mm tall | 10 mm | 3.3° |
| 90 mm wide, 175 mm tall | 5 mm | 1.6° |

The arm holds about 3 degrees. So the third row is not something to attempt,
and `needs_empty_neighbour()` says so. Leaving the slot beside it empty doubles
the effective spacing, which takes 1.6 degrees to 17.4 — the dotted lines in
the picture.

What makes this worth a function rather than a rule of thumb is that it depends
on the **measured** width and height. It is decided per glass, on the day, and
it is why the rack takes six glasses on one run and four on another.

Slots are filled furthest-from-the-arm first, so a glass already standing in
the rack is never between the arm and the next slot.

## Feeling for the rack

The height at which the rim lands is

    slot height + (glass height - grip height)

and *both* of those glass numbers were measured, so both carry error, and the
errors add. Driving to a calculated height is how a rim gets chipped.

`descend_until_contact()` comes down in 2 mm steps until the contact sensors on
the pads report something, up to a 60 mm limit. Two millimetres because a rim
meeting a peg at that step size is a touch rather than a knock.

Reaching the limit without touching anything is itself an answer — the glass is
not where it was thought to be — and it raises rather than carrying on.

## One last check before letting go

```python
if not self._arm.load_transferred(GRIPPER_WEIGHT_N):
    raise MotionFailed("the rack is not taking the weight, so the glass is caught")
```

Contact is not the same as support. A glass whose rim has caught on the edge of
a peg registers a contact while still hanging from the gripper, and opening the
fingers on it drops it.

The wrist sensor settles this. If the rack has taken the weight, the sensor is
back to reading the gripper alone. If it is not, the glass is still there in
the reading, and the arm says so instead of letting go.

Only then do the fingers open, MoveIt is told the arm is empty, and the arm
lifts away for the next glass.

## What the run reports

Both columns, with the same weight given to each:

```
finished: 4 racked, 0 left standing
  1. glass_0: straight_glass, 164 mm tall, 63 mm wide, 244 g, held 14 mm up, slot 5
  2. glass_1: stemmed_glass, 134 mm tall, 77 mm wide, 77 g, held 31 mm up, slot 4
  ...
```

A refused glass gets a line saying which one and why — "nowhere safe to hold
it: the rule wants the fingers 61 mm apart, outside the 4 to 40 mm a
stemmed_glass should ever need". That is a working run, not a failed one. The
run to worry about is the one that racks everything by ignoring a doubt.

← [Back to the walkthrough](README.md)
