# Problem 2 — the six solutions side by side

This page holds the scores of all six solutions in one place, and what they say
when set side by side. All six turn the same pictures into masks. All six are
scored by the bench described in
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

**Every solution is run twice**: once on the ordinary arrangements the cell's
layout rule makes, and once on crowded ones. So there are two tables below. Both
runs use the same three survey stations per arrangement, the same shared step
from mask to place, and the same scorecard. No solution was trained or tuned on
these arrangements.

**Each run is repeated over five blocks of 20 arrangements.** Twenty
arrangements is a small sample. A score from one block moves when the
arrangements change. Five blocks give 100 arrangements and about 500 glasses per
table. The numbers are the average of the five blocks. The brackets show the
lowest and highest block, so you can see which differences are real.

**The blocks vary the arrangements, not the training.** All five blocks use the
same fitted weights. So nothing here says how much a score would move if a
solution were trained again.

**Both runs use all four kinds of glass.** Each arrangement holds one kind, and
the kind changes from one arrangement to the next. The 100 glasses of the first
ordinary block are 26 straight, 25 tapered, 25 short stemmed and 24 stemmed. So
every number below is an average over the four kinds.

## The results

Each solution's own README explains its numbers. This page sets them side by
side.

### Spawned layouts — the spacing the cell's own layout rule gives

Every count is per 100 glasses, averaged over the five blocks, with the lowest
and highest block in brackets. The place and mask columns are the mean of the
five blocks' medians.

| | found per 100 | missed | merged | split | place | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 100.0 (100.0–100.0) | 0.0 | 0.0 | 0.0 | 6.8 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | **100.0** (100.0–100.0) | 0.0 | 0.0 | 0.2 | 8.3 mm | 99.1% | 0.0% |
| [2 trained from scratch](../02-train-from-scratch/) | 64.1 (62.4–66.7) | 35.9 | 0.0 | 0.0 | 0.6 mm | 98.3% | 1.6% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 6.4 (2.0–11.9) | 93.6 | 0.0 | 0.0 | 23.7 mm | 95.2% | 3.3% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | **99.4** (99.0–100.0) | 0.6 | 0.0 | 0.2 | 6.6 mm | 99.7% | 4.6% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 83.0 (78.0–86.1) | 17.0 | 0.0 | 0.2 | 5.6 mm | 97.2% | 0.0% |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | 96.4 (94.9–98.0) | 3.6 | 0.0 | 0.0 | 6.0 mm | 96.6% | 0.0% |

### Crowded layouts — closer than the layout rule allows

The columns are the same as in the table above.

| | found per 100 | missed | merged | split | place | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 86.4 (82.2–88.5) | 13.6 | 0.6 | 0.6 | 0.4 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | 73.0 (70.3–75.5) | 27.0 | 10.7 | 1.9 | 8.7 mm | 91.9% | 0.0% |
| [2 trained from scratch](../02-train-from-scratch/) | 74.6 (71.3–79.8) | 25.4 | 0.6 | 0.2 | 0.9 mm | 97.1% | 1.4% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 2.1 (0.0–4.2) | 97.9 | 0.0 | 0.0 | 39.1 mm | 96.0% | 4.9% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | 72.0 (70.8–72.9) | 28.0 | 0.8 | 1.0 | 0.6 mm | 99.2% | 3.7% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 73.6 (71.9–76.6) | 26.4 | 0.0 | 0.0 | 0.8 mm | 98.3% | 0.0% |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | **81.9** (77.2–86.5) | 18.1 | 1.4 | 0.4 | 0.5 mm | 97.2% | 0.0% |

**Read the brackets before the ranking.** On crowded layouts, solutions 1, 2, 4
and 5 have overlapping brackets. This test does not separate those four. Only
two statements survive: solution 6 is ahead, and solution 3 is far behind. On
spawned layouts the brackets separate everything except solutions 1 and 4. They
sit a fraction of a glass apart.

Solutions 5 and 6 have more than one rung. The rows above are rung `sam2` and
rung `modal`. The floor is `bench/floor.py` run with the renderer's own masks.
No segmenter can beat it. Even the floor misses 13.6 crowded glasses per 100,
because a glass wholly behind another is in no picture. So read the crowded
column against 86.4, not 100.

**Four of the six rows moved when one refusal was fixed.** Solutions 4, 5 and 6
each refused a report whose width no glass of the kind could have. Each did so
on a mask the frame had cut in half. With the bench's own exact masks, one
station at a time, the kind's range refuses 66 of 297 glass sightings. **Every
one of those 66 reaches the frame edge.** So the bench was refusing its own
perfect masks. `masks_to_glasses` now says whether a mask reached the picture's
edge, and the three solutions check it before refusing. Found on spawned
layouts went 92 → 99, 76 → 81 and 90 → 96. On crowded ones it went 66 → 73,
71 → 73 and 74 → 78. Solution 1 gained the width check its own document asks
for. Before it, solution 1 found 28 of 101 crowded glasses, with 21 merged
reports. After it, 71, with 10 merged.

## What the numbers mean

The [examiner](../../docs/02-segment-glasses/the-examiner.md#what-the-examiner-measures)
defines each measurement. In short:

**Found, missed, merged, split, false.** *Found* counts distinct real glasses
that got a report. A report is matched to a glass by its mask's pixels, not by
its place. *Missed* is the count to watch hardest, because a missed glass leaves
no trace.

**Position error.** How far a reported place is from the true one. **This number
saturates**, so the floor row is in both tables. A solution at the floor has
almost no error of its own.

**Mask covered, mask not the glass.** How much of the real glass the mask
covered, and how much of the mask was not that glass. These separate methods
when the places cannot. Both are medians over glasses, measured in the picture
the mask was drawn in.

**Averaging over four kinds hides something in the mask numbers.** The table
below opens it up once. It gives how much of the glass the mask covered at the
middle glass, kind by kind. It is from the first spawned block (`--from-seed
10000`), for the written rule and the fine-tuned model.

| kind | rules on the table | the same model, fine-tuned |
|---|---|---|
| straight | 99.5% | 99.7% |
| tapered | 100.0% | 99.8% |
| short stemmed | 88.7% | 99.7% |
| stemmed | 86.6% | 99.8% |

The written rule covers the two kinds without a stem almost completely. It loses
an eighth of the two kinds with a stem. A bowl-only outline misses the foot and
the sliver of stem beside it. So for a written rule, the stem is the hard part.
The fitted model covers all four kinds almost equally. Neither fact shows in the
single figures of 98.9 per cent against 99.8. That is why each solution's README
breaks the measurement down by kind.

## What the comparison says

**The written rule and the fitted network fail in opposite directions.**
Solution 1 finds every spaced glass in all five blocks. No other solution does.
On crowded layouts, only its width check stops a merged report, and that check
does not always hold. It finds 73.0 glasses per 100 against the 86.4 possible.
It still leaves 10.7 reports per 100 covering two glasses. Its place is 8.7 mm
off, against the floor's 0.4 mm. A cut drawn where the dots divide is not where
the glasses divide. Solution 2 merges almost nothing but misses a third of the
spaced glasses. A glass whose middle is outside the picture casts votes that
land nowhere. That is a limit of the voting design, not of its training.

**Borrowed weights carry the names, not the shapes.** Solution 3 finds 6.4
glasses per 100, with nothing merged, split or false. It finds a few objects
and calls them sports balls and frisbees. Solution 4 is the same model, library
and starting weights, trained further on this cell. That training also cuts the
category list to one class. The two changes cannot be separated, because a
model cannot learn this cell's labels while still naming household objects. So
nothing differs between solutions 3 and 4 except what training brought. The gap,
6.4 against 99.4, measures what that training bought. It is far larger than
either solution's spread across blocks. No draw of arrangements could produce it
by chance.

**Four of the six are not separated on crowded tables, and running five blocks
shows it.** Solutions 1, 2, 4 and 5 average 73.0, 74.6, 72.0 and 73.6 glasses
per 100. Each of the four has a block between 70 and 80. So their order is the
luck of the arrangements. Solution 2 has the widest spread of any solution, 71.3
to 79.8, and on one block it beats every other method. Only solution 6, at 81.9,
sits clear of the group.

**The two mask numbers disagree about who is best.** Solution 1's masks never
claim a pixel that is not glass, because a pixel joins a mask only if it stands
above the table. The fitted and borrowed models all claim a thin margin around
the glass, from 1.4 to 4.6 per cent. A learned outline follows a shape only
roughly. Neither habit shows in the places, so the mask is measured on its own.

## What these results do not cover

- **Not Gazebo.** The pictures come from `../bench/render.py`. It uses the wrist
  camera's lens and the cell's survey stations, but not the simulator. The arm
  never moves. No inverse kinematics or motion planning is checked.
- **Opaque glasses and clean depth.** No noise, no reflections, no
  transparency. This flatters the methods built on depth.
- **One table, one light.** Nothing in the rendering varies. A fitted model may
  learn the renderer's own constants as a clue, and no number here would show it.
- **Nothing about hidden glasses.** Every solution here reports only what some
  picture held. Finding a glass no picture held is
  [a shared step of its own](../../docs/02-segment-glasses/hidden-glasses.md).

## Reproducing

One block of 20 arrangements is one run, and `--from-seed` says which block.

```
pixi run python bench/floor.py --scenes 20 --from-seed 10000
pixi run python 01-rules-on-the-table/run.py --scenes 20 --from-seed 10000
pixi run python 01-rules-on-the-table/run.py --scenes 20 --from-seed 10000 --crowded
```

The five blocks on this page are `--from-seed 10000`, `10020`, `10040`, `10060`
and `10080`. The same two lines run each of the other five solutions. Every seed
at or above 10000 is held out. So any block in that range is one no training
has seen. Then average them:

```
pixi run python bench/average_blocks.py
pixi run python bench/average_blocks.py --crowded
```

The fitted solutions need their training step first. Each README says which.
