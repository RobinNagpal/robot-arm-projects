# Step 4: lift straight up, out of the holders

[← step 3](03-grip-the-edge.md) · [index](README.md) · next: [step 5 →](05-carry-round.md)

**The same code as the wrist turn.** The full explanation is in
[the wrist docs, step 4](../turn-by-wrist/04-lift-out.md).

![Before and after the lift: every height, the holders, and why 16.5 + 4 cm](../turn-by-wrist/figures/lift_out.png)

## What happens

The tool goes **straight up**, at a tenth of full speed, keeping its
orientation. Only the shoulder, the elbow and wrist 1 move.

**How far:** the robot never sees the holders, so it cannot size the lift to
them. But whatever holds the board up must be lower than its upper edge, which
the fingers just reached freely. So the **lower edge** is lifted past where the
upper edge was, plus a margin:

```
lift = board height + LIFT_CLEAR = 16.5 + 4 = 20.5 cm
```

## Seed 1

| | Before | After |
| --- | --- | --- |
| tool0 | 28.6 cm | 49.1 cm |
| upper edge | 16.6 cm | 37.1 cm |
| lower edge | 0.1 cm | 20.6 cm |

The lift is checked for collisions first. If MoveIt refuses, because the top
still touches things at the start, it is run unchecked. Then the fingertips
must still feel the top.

The lift does not need `H`: when the tool moves **without turning**, the top
moves by exactly the same amount.

## Anything different for the whole-arm turn?

No.

[← step 3](03-grip-the-edge.md) · [index](README.md) · next: [step 5 →](05-carry-round.md)
