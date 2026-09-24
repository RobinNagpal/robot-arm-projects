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

| Step | What does it | How |
|---|---|---|
| 1. Find | `find.py` | Every pixel above the table becomes a point in the room. The points are grouped by where they stand on the table, in 5 mm squares, joined within 25 mm. The middle of each group's top points is the glass's axis. |
| 2. Choose a place | `views.py` | The same veto as the learned version: out of reach, or a glass squarely in the way. Then the rule: the widest gap, as an angle at the camera, between the target and any glass that would cover it or join its outline. A glass in front always counts; one behind counts only inside the depth band. Ties go to the place nearest the middle of the arm's reach. |
| 3. Measure | `measure.py` | Problem 1's silhouette, then three checks: the glass is not cut off at the frame edge, the outline is not ragged, and its widest width agrees within 6 mm with the width seen from above. Then two corrections worked out from where the lens is (below). |

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
