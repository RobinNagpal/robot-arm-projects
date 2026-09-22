# Step 3: grip the middle of the upper edge

[← step 2](02-plan-before-moving.md) · [index](README.md) · next: [step 4 →](04-lift-out.md)

**The same code as the wrist turn.** The full explanation is in
[the wrist docs, step 3](../turn-by-wrist/03-grip-the-edge.md), including the
hold `H` worked through with seed 1's matrices.

![The grip in four pictures: open above, down, closed, and every height with its name](../turn-by-wrist/figures/grip_moves.png)

## What happens

1. Open the fingers to thickness + 3 cm: 1.9 + 3 = **4.9 cm**.
2. Free move to **8 cm above** the grip, wrist the way step 2 chose.
3. Take the top out of MoveIt's picture, so the fingers may touch it.
4. **Straight down 8 cm.** tool0 stops 12 cm above the edge, so the fingertips
   (17 cm below tool0) reach **5 cm** past it and both rows of pads are on the
   board.
5. Close to thickness − 4 mm. The fingers stop on the board and squeeze. The
   fingertip sensors must feel it within 2 s.
6. Tell MoveIt the top is **attached** to the gripper.

## Seed 1

| Pose | tool0 | Fingertips |
| --- | --- | --- |
| approach | 36.6 cm | 3 cm above the edge |
| pick | 28.6 cm | 5 cm below the edge |

## The hold

```
H = P⁻¹ · T         P: the top in the room      T: the tool in the room, at the grip
```

`H` is the tool's pose **measured from the top**. For seed 1, tool0 is 20.2 cm
along the top's own "up" axis, pointing back at it. While the top stays in the
fingers, `H` never changes, and

```
top  = tool · H⁻¹        tool = top · H
```

## Anything different for the whole-arm turn?

The grip itself, no. But the two rows of pads matter just as much here: once
the top is flat, its weight twists it in the fingers with the same 0.17 N·m in
both turns ([step 7, continued](07-what-each-joint-does.md#the-load-on-the-grip)).

And `H` has one extra job in this turn. `gripped_edge()` finds the edge to
turn about from the tool's pose alone, as "12 cm along the tool's reach". That
is the same fact `H` records, written from the tool's side
([step 7](07-turn-about-the-edge.md#7a-the-pivot-and-the-line-to-turn-about)).

[← step 2](02-plan-before-moving.md) · [index](README.md) · next: [step 4 →](04-lift-out.md)
