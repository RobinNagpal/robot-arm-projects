# Step 6: line the gripped edge up with wrist 1's axis

[← step 5](05-carry-round.md) · [index](README.md) · next: [step 7 →](07-turn-flat.md)

## What happens

This is not a separate move. It is **how the end of the carry was chosen** in
step 2, and it is what makes the turn in step 7 work. By the end of the carry,
the gripped edge runs exactly along wrist 1's axis.

This page explains why that matters, why wrist 1's axis is not simply the
room's y axis, and how the code finds it.

**Joints that move:** none of their own. The line-up happens during the carry,
through the base and wrist 3.

![Seen from above: the arm's plane runs 13.3 cm to one side of the base, so wrist 1's axis is 15.5° off square; and what happens if the edge is not lined up](../figures/wrist_axis.png)

## What comes in

| From | Value | Seed 1 |
| --- | --- | --- |
| step 2 | the turning spot | (50, 0, 40) cm |
| the robot's model | how the UR5e's links are laid out | – |

---

## 6a. Why the edge must run along the axis

When wrist 1 turns, **everything beyond it turns about wrist 1's axis**: wrist
2, wrist 3, the gripper and the top in its fingers. Think of a door turning on
its hinge.

The top hangs straight down. To end **flat**, it has to turn a quarter turn
about a **level line running along its gripped edge**, the way a drawbridge
comes down.

- **Axis along the edge:** the top swings up like a drawbridge and ends flat.
- **Axis at an angle φ to the edge:** the top also swings sideways, and ends
  **φ off flat**.

That second case is tested in the code:
`test_a_board_whose_edge_is_off_the_axis_does_not_end_flat` puts the edge 15°
off the axis, and the top ends 15° off flat.

So before the turn, **the gripped edge must point exactly along wrist 1's
axis**.

---

## 6b. Why the axis is not the room's y axis

A first guess: the turning spot is straight in front of the arm, along x. The
arm reaches straight out along x, so wrist 1's axis, square to the reach, runs
along y.

That would be right if the arm's links sat on one line above the base's
centre. **They do not.** The UR5e's upper arm, forearm and wrist step sideways
from the base, **13.3 cm in all** (the `0.1333` in the robot's description).

So the arm's upright plane, the plane the shoulder, elbow and wrist 1 move the
tool in, runs **13.3 cm to one side of the base's centre**.

### The triangle, seen from above

To put the tool over a point 50 cm from the base, the base turns until that
plane passes through the point:

```
   the arm's plane  ─────────────────• turning spot
   (seen from above,                /|
    it is a line)                  / |
                         50 cm    /  | 13.3 cm, the sideways offset
                                 /   |
                                /φ   |
                         base  •-----+
                                 parallel to the arm's plane
```

The arm's plane passes through the turning spot, 13.3 cm to the side of the
base, and runs parallel to the bottom side of the triangle. The line from the
base to the spot is the room's x axis. The angle φ between the two is how far
the arm's plane is turned from x. The offset sits opposite φ, and the 50 cm to
the spot is the long side. So:

```
sin φ = 13.3 / 50 = 0.267        φ = arcsin 0.267 = 15.5°
```

The arm's plane is turned 15.5° from the room's x axis, and **wrist 1's axis,
square to that plane, is turned 15.5° from the room's y axis**. That is also
why, at the turning spot, the base joint is at −15.5°, not 0°.

In 3D, a level direction 15.5° round from y is

```
axis = (sin 15.5°, cos 15.5°, 0) = (0.267, 0.964, 0)
```

---

## 6c. How the code finds the axis

The code does not use that triangle. It asks the robot's own model, so nothing
is assumed about how the links are laid out. If the arm were a different
model, the same code would still work.

`Arm.joint_axis(joints, WRIST_1)` in `arm/motion.py`:

### 1. Pick a trial pose at the spot

In `_plan_route()` (step 2):

```
trial = tool pointing straight down, tool0 12 cm above the spot, x along the room's x
joints = solve(trial)
```

### 2. Nudge wrist 1 and see how the tool turned

```python
nudged = joints.copy()
nudged[WRIST_1] += 0.1                                  # 0.1 rad, about 5.7°
before = forward(joints)[:3, :3]                        # the tool's orientation
after  = forward(nudged)[:3, :3]
axis   = turn_axis(before, after)
```

`forward()` is forward kinematics: joint angles in, tool pose out.

### 3. Read the axis out of the turn

`turn_axis()` in `transforms.py`:

```
turn = after · beforeᵀ            the rotation that happened
axis = ( turn[2,1] − turn[1,2],
         turn[0,2] − turn[2,0],
         turn[1,0] − turn[0,1] ),  made length 1
```

**Why that works.** `beforeᵀ` undoes the starting orientation, so `turn` is
just the change. Any rotation by an angle θ about a unit axis k has this
shape:

```
turn = I + sin θ · K + (1 − cos θ) · K²       (Rodrigues' formula)

where  K = [  0   −k₃   k₂ ]
           [  k₃   0   −k₁ ]
           [ −k₂   k₁   0  ]
```

`I` and `K²` are symmetric: flipping them across the diagonal changes nothing.
`K` is the opposite: each number across the diagonal is minus the other. So
subtracting a matrix element from its mirror image cancels the symmetric parts
and doubles `K`'s:

```
turn[2,1] − turn[1,2] = sin θ · (k₁ − (−k₁)) = 2 sin θ · k₁
turn[0,2] − turn[2,0] = 2 sin θ · k₂
turn[1,0] − turn[0,1] = 2 sin θ · k₃
```

That is the axis times 2 sin θ. Making it length 1 leaves the axis. It also
comes out pointing the way that makes the turn positive, anticlockwise about
it.

### Seed 1

```
axis = (0.267, 0.964, 0.000)
angle from the y axis = arctan(0.267 / 0.964) = 15.5°
```

It matches the triangle.

### Found once

The axis depends only on **where** the tool is, not on how it is spun about the
vertical. Wrist 3 spins the tool about its reach without moving wrist 1. So one
trial pose is enough.

---

## 6d. Making the edge run along it

`hanging_tool_poses(spot, axis)` in `assembly/grasps.py` gives the two poses
the carry can end at:

```
tool pointing straight down, tool0 12 cm above the spot, tool x along +axis
tool pointing straight down, tool0 12 cm above the spot, tool x along −axis
```

The gripped edge always runs along the tool's x (step 2, `down_tool_pose()`).
So in both, **the edge runs along wrist 1's axis**. Either one lines the top up.
They differ by half a turn of wrist 3, and step 2 took the one needing less:
+axis for grip A, about 13.6° of wrist 3 on the way
([step 5](05-carry-round.md#who-does-the-turning-base-or-wrist-3)).

### The arm at the start of the turn

At the hanging pose, the joint angles are, in degrees:

| base | shoulder | elbow | wrist 1 | wrist 2 | wrist 3 |
| --- | --- | --- | --- | --- | --- |
| −15.5 | −91.2 | 86.5 | −85.3 | −90.0 | 0.0 |

Two checks by hand:

- **Base at −15.5°**: the arm's plane is turned by φ, as in 6b.
- **The tool points straight down**: the shoulder, elbow and wrist 1 turn about
  parallel lines, so the tool's tilt in the arm's plane is their sum:

  ```
  −91.2 + 86.5 + (−85.3) = −90.0°        straight down
  ```

(These angles come from [`../figures/two_turns.py`](../figures/two_turns.py),
which runs the same planning on the same robot model Gazebo uses. The real
run's angles may differ slightly.)

---

## What goes out

| Value | Seed 1 | Used in |
| --- | --- | --- |
| wrist 1's axis at the spot | (0.267, 0.964, 0) | step 2 (hanging poses), step 7 |
| the gripped edge along that axis | – | step 7 |
| the joint angles at the start of the turn | the table above | step 7 |

## Fixed and measured numbers in this step

| Number | Value | Kind | Where |
| --- | --- | --- | --- |
| the arm's sideways offset | 13.3 cm | robot fact | the UR5e's description |
| nudge | 0.1 rad | choice | `arm/motion.py`, `joint_axis()` |
| wrist 1's axis, φ | (0.267, 0.964, 0), 15.5° | **worked out** from the model | |

## Where it is in the code

| What | Where |
| --- | --- |
| the trial pose, finding the axis once | `task.py`: `_plan_route()` |
| nudging a joint to find its axis | `arm/motion.py`: `joint_axis()`, `forward()` |
| the axis of a rotation | `transforms.py`: `turn_axis()` |
| the two hanging poses | `assembly/grasps.py`: `hanging_tool_poses()` |
| the test of an edge off the axis | `test/test_grasps.py`: `test_a_board_whose_edge_is_off_the_axis_does_not_end_flat` |

[← step 5](05-carry-round.md) · [index](README.md) · next: [step 7 →](07-turn-flat.md)
