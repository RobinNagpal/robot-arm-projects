# Step 6: line the gripped edge up with wrist 1's axis

[← step 5](05-carry-round.md) · [index](README.md) · next: [step 7 →](07-turn-about-the-edge.md)

The line-up itself is **the same as the wrist turn**: the carry ends with the
gripped edge running along wrist 1's axis. How the axis is found, and why it is
15.5° off the room's y axis, is in
[the wrist docs, step 6](../turn-by-wrist/06-line-up-with-wrist-1.md).

**What is different is why it matters.**

![Seen from above: the arm's plane runs 13.3 cm to one side of the base, so wrist 1's axis is 15.5° off square](../figures/wrist_axis.png)

## The short version of how

- The UR5e's links step **13.3 cm sideways** from the base. So the arm's upright
  plane, where the shoulder, the elbow and wrist 1 move the tool, runs 13.3 cm
  to one side.
- To reach a spot 50 cm out, that plane is turned by φ, with
  `sin φ = 13.3 / 50`, so **φ = 15.5°**. Wrist 1's axis, square to the plane, is
  15.5° off the room's y axis: **(0.267, 0.964, 0)**.
- The code does not use that formula. It nudges wrist 1 by 0.1 rad on the
  robot's model and reads the axis out of how the tool turned
  (`joint_axis()`, `turn_axis()`).
- The hanging pose at the spot has the tool's x, and so the gripped edge, along
  that axis.

---

## Why it matters for the wrist turn

The wrist turn turns the top about **wrist 1's axis**. If the edge is at an
angle to that axis, the top ends **tilted** by that angle. The line-up is what
makes the wrist turn end flat at all.

## Why it matters for the whole-arm turn

The whole-arm turn turns the top about **the edge itself**, whichever way the
edge points. So **it would end flat anyway**, lined up or not.

What the line-up buys is **simplicity**:

### Lined up: the turn lies in the arm's plane

The edge runs along wrist 1's axis, which is square to the arm's plane. A turn
about a line square to a plane moves every point **within** planes parallel to
it. So tool0 moves on a circle **in the arm's plane**, and the tool tilts
**in the arm's plane**.

That is exactly what three joints can do on their own: the shoulder, the elbow
and wrist 1 turn about parallel lines square to that plane. Between them they
can put tool0 anywhere in the plane (shoulder and elbow) and tilt it to any
angle in the plane (all three):

```
tool tilt = shoulder + elbow + wrist 1
```

**The base, wrist 2 and wrist 3 have nothing to do.** In Gazebo they moved
0.0°.

### Not lined up: everything joins in

Suppose the edge ran along the room's y axis instead, 15.5° off wrist 1's axis.
The circle tool0 has to follow would be tipped 15.5° out of the arm's plane.
To follow it:

- **the base** would have to turn, to swing the arm's plane round as tool0
  moves sideways out of it;
- **wrists 2 and 3** would have to turn, to tilt the tool about a line the
  three parallel joints cannot tilt it about.

All six joints moving at once, in a coordinated way, with a top held by
friction. It would still end flat, but it would be a harder path for MoveIt to
find and follow.

## Seed 1, at the start of the turn

The same pose as the wrist turn, in degrees:

| base | shoulder | elbow | wrist 1 | wrist 2 | wrist 3 |
| --- | --- | --- | --- | --- | --- |
| −15.5 | −91.2 | 86.5 | −85.3 | −90.0 | 0.0 |

The tilt rule: −91.2 + 86.5 − 85.3 = −90.0°, the tool pointing straight down.

[← step 5](05-carry-round.md) · [index](README.md) · next: [step 7 →](07-turn-about-the-edge.md)
