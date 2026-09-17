# Step 5: carry it round, hanging

[← step 4](04-lift-out.md) · [index](README.md) · next: [step 6 →](06-line-up-with-wrist-1.md)

**The same code as the wrist turn.** The full explanation is in
[the wrist docs, step 5](../turn-by-wrist/05-carry-round.md).

![The carry from above, the top's centre on an arc round the base, and every height along the way](../turn-by-wrist/figures/carry_arc.png)

## What happens

The top is carried from the arm's left to the turning spot in front, still
hanging straight down. The path is planned for **the top's centre**, then
turned into tool poses with `H`.

- **On an arc, not a straight line.** Distance from the base and angle round
  it both change evenly: 54 → 50 cm, 91.4° → 0°. A straight line would pass
  36 cm from the base and make the arm fold up.
- **At one height.** The top's centre rises 3 cm at the start, to 31.75 cm,
  the height it will hang at, at the turning spot. After that it never
  changes.
- **Turning only about the vertical.** The tool turns −104.9° on the way, so
  the edge ends along wrist 1's axis. Turning about a vertical line cannot tip
  a hanging board. The base does −91.4° of it; wrist 3 adds about 13.6°.
- **22 poses**, one every 5° of whichever turns more, then the hanging pose
  once more.
- Straight lines between poses at a tenth of full speed, every point
  collision-checked with the top attached. If that fails, MoveIt plans one free
  move to the end, keeping the arm's shape. Then the fingertips must still feel
  the top.

## Seed 1

| | tool0 | the top's centre | the edge runs along |
| --- | --- | --- | --- |
| start | (−1.3, 54.0, 49.1) cm | (−1.3, 54.0, 28.8) cm | (−1, 0.01, 0) |
| end | (50.0, 0.0, 52.0) cm | (50.0, 0.0, 31.75) cm | (0.267, 0.964, 0) |

## Anything different for the whole-arm turn?

No. The carry ends at the same hanging pose, with the edge along wrist 1's
axis. [Step 6](06-line-up-with-wrist-1.md) explains why that still matters for
this turn, for a different reason.

[← step 4](04-lift-out.md) · [index](README.md) · next: [step 6 →](06-line-up-with-wrist-1.md)
