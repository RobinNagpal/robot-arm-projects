# Step 1: look round and measure the top

[index](README.md) · next: [step 2 →](02-plan-before-moving.md)

**The same code as the wrist turn.** The full explanation, with every formula,
is in [the wrist docs, step 1](../turn-by-wrist/01-look-and-measure.md). This
page is the short version.

![The fitted box seen from the arm: centre, along, up, and the edge formula](../turn-by-wrist/figures/board_box.png)

## What happens

1. **Survey.** The camera looks from eight places round the base, 30 cm out
   and 60 cm up, aimed at the floor 65 cm out.
2. **Pixels to points.** Colourful pixels are parts; grey pixels are the floor
   and everything else. Each pixel's depth turns it into a point in the room:
   `x = (u − cx) · z / fx`, then the camera's pose puts it in room coordinates.
3. **Read the room.** The floor is the most common height of grey points. The
   coloured points are grouped into objects. The broadest thin plate is the
   table top; long thin ones are legs. Grey things standing on the floor are
   obstacles. The holders are grey and touch the top, so they are dropped as
   its shadowed side: **the robot never sees them**.
4. **Fit a box to the top.** The face's plane gives the normal; the vertical
   flattened onto the face gives `up`; `along = up × normal`. Measured along
   those three arrows, the spread of the points gives the size, and the middle
   of each spread gives the centre.
5. **Measure again close up**, from four views 40 cm away.
6. **Two checks.** Thinner than 6.5 cm? Leaning less than 5°?
7. **The middle of the upper edge:** `edge = centre + up × width / 2`.

## Seed 1

| Value | Seed 1 | Kind |
| --- | --- | --- |
| floor | 0.0 cm | measured |
| the top's size | 24.4 × 16.5 × 1.9 cm | measured |
| its centre | (−1.3, 54.0, 8.3) cm | measured |
| `along`, `up`, `normal` | (−1, 0.01, 0), (0, 0, 1), (0.01, 1, 0) | measured |
| lean | 0.0° (limit 5°) | measured |
| the middle of the upper edge | (−1.3, 54.0, 16.6) cm | worked out |

## Anything different for the whole-arm turn?

No. Everything here is used the same way by both turns.

[index](README.md) · next: [step 2 →](02-plan-before-moving.md)
