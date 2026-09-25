# Problem 2 — the programmed way

The same job as `../problem-2-learned`, done with geometry and written rules
only. No training data, no model, no weights.

## The workflow

```
1. overhead depth picture ──points above the table──▶ group them on the table ──▶ each glass
2. 24 places round each glass ──veto──▶ allowed ──order by gap in the picture──▶ best first
3. side picture ──silhouette──▶ checks ──▶ height correction ──▶ profile
   a check fails ──▶ next place, up to 3 ──▶ still failing: hand to problem 3
```

**1. Find — `find.py`.**
- Turn every pixel above the table into a point in the room.
- Group the points by where they stand on the table, not where they are in
  the picture. Two glasses can overlap in the picture but are always apart on
  the table.
- Each group is one glass. The middle of its top points gives its place,
  and the spread of its points gives its width.

**2. Choose a place — `views.py`.**
- Try 24 places in a circle round the glass. Throw out the same ones as the
  learned version: out of reach, or a glass squarely in the way.
- Order the rest by one rule: how big is the gap, in the picture, between the
  target and the nearest glass that could cover it or join its outline. A
  glass behind counts only if it is close behind. Ties go to the place the arm
  reaches most easily.

**3. Measure and check — `measure.py`.**
- Take the side picture from the best place and cut out the glass's outline.
- Check it. The picture is refused if the glass runs off the edge, or if its
  widest width differs from the width seen from above by more than 6 mm (a
  sign another glass is in the outline).
- If it passes, read the profile and correct the height (below).
- If it fails, try the next place, up to 3. If all 3 fail, hand the glass
  to problem 3.

**The height correction.** The camera looks level from 120 mm up. Above that
height the top of the outline is the near side of the rim, which is nearer
than the glass's axis and so reads high. Below it, the bottom of the outline
is the near side of the foot. Both distances are known, so both errors can be
undone. Uncorrected, a tall glass reads 5–17 mm tall. Corrected, it is within
2 mm.

## Running it

```
make run        # the 50 held-out scenes; writes results.json
make test
```

## Results — the same 50 held-out scenes, 250 glasses

| Step | Result |
|---|---|
| Find | 250 found, 0 missed, merged or split. Position 0.2 mm median, 1.2 mm worst |
| Choose | first place unspoiled 246 of 250; a random allowed place 223 of 250. 2 handed over, both caught by the width check |
| Measure | height 0.8 mm median, 2.3 mm worst; width 1.7 mm median |

The scenes, the renderer and the scoring are in `../problem-2-sim`, shared with
`../problem-2-learned`. Compare the two `results.json` files.
