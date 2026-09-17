# Step 1: look round and measure the top

[index](README.md) · next: [step 2 →](02-measure-the-legs.md)

**The same code as the turns in the air.** The full explanation, with every
formula, is in [the wrist docs, step 1](../turn-by-wrist/01-look-and-measure.md).

![Where the camera looks from: eight survey views round the base, and four close views of the top](../turn-by-wrist/figures/survey_views.png)

## What happens

1. **Survey.** Eight pictures all round the base: camera 30 cm out, 60 cm up,
   looking at the floor 65 cm out.
2. **Pixels to points.** Colourful pixels are parts; grey ones are the floor and
   everything else. Each pixel's depth makes it a point in the room.
3. **Read the room.** The floor is the most common height of grey points.
   Coloured points are grouped into objects and told apart **by shape**:
   - the broadest thin **plate** is the table top;
   - a **stick**, longest side more than twice the next, is a leg;
   - grey things standing on the floor are obstacles.
4. **Measure the top close up**, from four views, and check it: thinner than
   6.5 cm, leaning less than 5°.
5. **The middle of its upper edge:** `edge = centre + up × width / 2`.

## What is different for the tilt

**The legs matter now.** In the air turns, the legs were only things to keep
clear of. Here they are where the top goes. The survey is what first finds
them: four sticks, far off to the arm's right. They are measured properly in
[step 2](02-measure-the-legs.md).

The turning spot in front of the arm is not used, and its 40 cm clear-space
check is not made.

## Seed 1

| Value | Seed 1 | Kind |
| --- | --- | --- |
| floor | 0.0 cm | measured |
| the top | 24.4 × 16.5 × 1.9 cm, centre (−1.3, 54.0, 8.3) cm | measured |
| the middle of its upper edge | (−1.3, 54.0, 16.6) cm | worked out |
| legs seen | 4 | measured |

## What can go wrong

As for the air turns, and one more: if the survey finds fewer than four legs,
step 2 stops with *"found N legs, and a table needs 4"*.

[index](README.md) · next: [step 2 →](02-measure-the-legs.md)
