# Step 5 — how hard to squeeze

The arm knows where to hold the glass and how far apart to put the fingers. How
hard they press is a separate question, and it is the one the camera cannot
answer at all.

Code: `glasses/force.py`, and `_pick_up()` in `task.py`.

## The sum, when you know the weight

A held object stays held because friction beats gravity:

    force >= mass * g / (friction * number of pads)

With silicone on glass, `GRIP_FACTOR` is 0.6, and there are two pads.
`SAFETY_FACTOR` doubles the answer, because friction coefficients are
optimistic and a glass that starts sliding does not stop.

So a 300 g glass wants about 5 N. That is the whole calculation, and it is not
the hard part.

## The part the camera cannot see

The hard part is `mass`.

The profile gives the outside of the glass exactly. It says nothing about the
**wall thickness**, and wall thickness is what decides the weight. A
thin-walled 190 mm champagne flute weighs less than a squat 90 mm tumbler, and
from outside there is no way to tell which you are looking at.

`estimate_mass()` does what can be done: the glass is a shell, so the volume
that matters is the surface swept by the outline times a thickness, plus a
solid disc for the base. The thickness comes from the kind — "thin", "normal",
"thick" — which is a category, not a measurement.

The estimate is wrong by roughly a third in either direction.

![Why the glass is weighed rather than trusted](../images/force-from-mass.png)

The line is the squeeze the arm starts with. The band is where the right answer
actually is. A third is fine for a first squeeze and useless as a final one.

## So the grip has three stages

**Stage one: take up the slack.** `CONTACT_FORCE_N` is 1 N — enough to close
the fingers onto the glass, not enough to do anything to it. The moment the
fingers stop is the moment they are touching, and the gap they stopped at is
the **true width of the glass, measured by touch**.

That number is then checked against what the camera predicted:

```python
if abs(touched - grip.opening) > 0.004:
    raise MotionFailed(...)
```

Four millimetres, because the camera measurement is good to about one (see
[step 2](step2-measuring-one.md)) and a tolerance tighter than the measurement
reports noise as failure. What this catches is the grasp being in the wrong
*place* — fingers that close at 40 mm where the stem should have been are
fingers around the bowl, and that is worth stopping for.

**Stage two: squeeze to the estimate, lift 10 mm, and weigh it.** The wrist
force sensor reads everything hanging below it, so subtracting the known weight
of the gripper leaves the glass.

The ten millimetres is deliberately small. This is the last moment a mistake is
free: the glass is off the table, nothing has been turned over, and setting it
back down costs nothing.

**Stage three: correct.** If the glass is heavier than it looked, it needs a
firmer grip — and the arm **puts it down first**:

```python
self._arm.move_linear([make_pose(position, rotation)])   # back on the table
self._arm.set_gripper_force(needed)
```

Increasing the squeeze on a glass already in the air arrives as a step change
in force, and a step change is what cracks a thin wall. Setting it down,
re-gripping and lifting again costs two seconds.

## Refusing is part of the design

Each kind has a `force_cap_n` — 6 N for thin-walled, 12 for normal, 20 for
thick. If the weight that comes back demands more than the cap,
`force_for_measured_mass()` raises `TooHeavyToHold` and the glass goes in the
refused column.

This is the case a project without a weighing step cannot even detect. A heavy
glass with thin walls looks, from outside, exactly like a light one. Without
the lift, the arm would simply squeeze harder until something gave.

## Commanding a force at all

A position controller cannot express any of this. Told to close to 9 mm on a
9 mm stem, it keeps driving towards 9 mm, and what happens next depends on the
joint's effort limit rather than on anything the task decided.

So the gripper has two controllers on the same two joints —
`gripper_controller` on position, `gripper_force_controller` on effort — and
only one runs at a time. `set_gripper_force()` hands the joints over when the
pads reach the glass; `set_gripper()` takes them back to let go. Letting go is
a position command, not a force of zero: zero force leaves the fingers limp
with the glass still sitting in them.

## Watching for slip

The squeeze can still be wrong, and the way to find out is to ask the glass.

`is_slipping()` compares the finger gap now against the gap when the glass was
gripped. Fingers that have crept closed mean the glass is sliding down through
the pads — there is no other reason for the gap to shrink.

It is checked during a slow 20-degree lean, and the angle is the point. Twenty
degrees puts some of the weight on the pads sideways, which is what makes a
marginal grip fail, and a glass leaning 20 degrees can be brought back upright.
A glass at 180 degrees cannot.

→ [Step 6 — turning it over and standing it down](step6-turning-it-over.md)
