# Problem 2 — the six solutions side by side

Six ways of turning the same pictures into the same masks, all scored on the
bench described in
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

**Every solution is run twice**, once on the ordinary arrangements the cell's
own layout rule produces and once on crowded arrangements that stand the glasses
closer than that rule allows, which is why there are two tables below rather
than one. Each run uses the same 20 held-out arrangements, the same three survey
stations per arrangement, the same shared arithmetic turning a mask into a place
and a width, and the same scorecard. None of the six was trained or tuned on
these arrangements. Every number here comes from a folder's own `results.json`.

## The results

Each solution's own README explains its numbers; this page only sets them side
by side.

### Spawned layouts — 100 glasses, the spacing the cell's own layout rule gives

| | found | missed | merged | split | false | position median · worst | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 100 | 0 | 0 | 0 | 0 | 6.3 · 46.5 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | **100** | 0 | 0 | 0 | 0 | 8.5 · 46.5 mm | 98.9% | **0.0%** |
| [2 trained from scratch](../02-train-from-scratch/) | 63 | 37 | 0 | 0 | 0 | **0.5** · 19.1 mm | 98.2% | 1.5% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 10 | 90 | 0 | 0 | 0 | 28.1 · 36.3 mm | 100.0% | 4.3% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | 99 | 1 | 0 | 0 | 0 | 5.5 · 46.5 mm | **99.8%** | 4.4% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 81 | 19 | 0 | 0 | 0 | 3.0 · 43.1 mm | 96.8% | **0.0%** |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | 96 | 4 | 0 | 0 | 0 | 4.5 · 42.2 mm | 96.7% | **0.0%** |

### Crowded layouts — 101 glasses, closer than the layout rule allows

| | found | missed | merged | split | false | position median · worst | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 83 | 18 | 1 | 1 | 0 | 0.4 · 50.0 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | 71 | 30 | 10 | 1 | 0 | 6.0 · 58.2 mm | 94.6% | **0.0%** |
| [2 trained from scratch](../02-train-from-scratch/) | 72 | 29 | 1 | 0 | 0 | 0.7 · 43.8 mm | 97.2% | 1.4% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 4 | 97 | 0 | 0 | 0 | 36.5 · 46.6 mm | 84.5% | 3.6% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | 73 | 28 | 1 | 0 | 0 | 0.9 · 74.5 mm | **99.3%** | 3.9% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 73 | 28 | 0 | 0 | 0 | 1.0 · 28.7 mm | 98.4% | **0.0%** |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | **78** | 23 | 3 | 2 | 0 | **0.5** · 58.4 mm | 97.3% | **0.0%** |

Solutions 5 and 6 have more than one rung; the rows above are rung `sam2` and
rung `modal`. The floor is `bench/floor.py` with the renderer's own masks, which
no segmenter can improve on. Even it misses 18 crowded glasses, because a glass
standing wholly behind another is in no picture at all.

**Four of the six rows moved when one refusal was repaired.** Solutions 4, 5 and
6 each refused a report whose width no glass of the kind could have, and each
made that refusal on a report measured from a mask the frame had cut in half.
Handed the bench's own exact masks, one station at a time, the kind's range
refuses 66 of 297 glass sightings and **every one of those 66 reaches the frame
edge** — the bench refusing its own perfect masks. `masks_to_glasses` now says
whether a mask reached the picture's edge and the three solutions read it before
refusing: 92 → 99, 76 → 81 and 90 → 96 found on spawned layouts, 66 → 73,
71 → 73 and 74 → 78 on crowded ones. Solution 1 gained the width check its own
document prescribes and never had, which is where its two rows come from: 28 of
101 crowded glasses with 21 merged reports before it, 71 with 10 after.

## What the numbers mean

**Found, missed, merged, split, false.** *Found* is how many distinct real
glasses got a report, judged by the pixels of the mask rather than by where the
report said the glass was. *Missed* is a real glass that got no report at all,
and it is the count to watch hardest: a split glass announces itself and a
merged pair looks like one large glass, but a missed glass leaves no trace
anywhere in the run.

**Position error.** How far a reported place sits from where the glass really
stands. **This number saturates**, which is why the floor row is in both tables:
the shared arithmetic takes the axis from the rim and the width from a
percentile precisely so that a ragged mask edge cannot move the answer, so two
quite different masks can give almost the same place. A solution at the floor is
not a good solution so much as one whose remaining error is not its fault.

**Mask covered, mask not the glass.** How much of the real glass the mask
covered, and how much of the mask was not that glass. These are the
measurements that separate methods when the places cannot. The first falls when
an outline loses a thin stem; the second rises when an outline leaks onto the
table or swallows a neighbour. Both are medians over glasses, measured in the
picture the mask was drawn in, and each solution's README breaks them down by
kind of glass.

## What the comparison says

**The written rule and the fitted network fail in opposite directions.**
Solution 1 finds every glass the layout spaces, and on the crowded layouts the
only thing standing between its one grouping distance and a merged report is the
check on the width: 72 groups there held more than one glass, 69 of them were cut
apart into two to nine parts, and 3 were handed over. That recovers 71 of the 83
any method could find, at the price of 10 reports still covering two glasses and
a place 6.0 mm from the truth against the floor's 0.4 mm, because a cut drawn
where the dots divide is not where the glasses divide. Solution 2 merges almost nothing and misses 37 glasses
on the easy layouts, because a glass whose middle falls outside the picture casts
votes that land nowhere — a limit of the voting design rather than of its
training.

**Borrowed weights carry the names, not the shapes.** Solution 3 finds 10 of
100 with nothing merged, split or false: it locates the objects and calls them
sports balls and frisbees. Continuing its training on this cell and cutting the
vocabulary to one class is solution 4, and the gap between the two — 10 found
against 99 — is the measurement of what that training bought.

**The two mask numbers disagree about who is best, and that is the useful
result.** Solution 1's masks almost never claim a pixel that is not glass at the
median (0.0%), because a pixel reaches a mask only by standing above the table —
though a part cut out of a run-together group can be mostly its neighbour, which
is what its 79.3% worst case on the crowded layouts is; the
fitted and borrowed models all claim a thin margin around the glass (1.4–4.4%)
because a learned outline follows a shape coarsely. Neither habit is visible in
the places at all.

## What these results do not cover

- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens and the cell's own survey stations, but not the simulator.
  The arm never moves, and no inverse kinematics or motion planning is checked.
- **Opaque glasses and clean depth.** No noise, no reflections, no
  transparency, which flatters the methods built on the depth reading.
- **One table, one light.** Nothing about the rendering is varied, so a model
  fitted here is free to use the renderer's own constants as a clue, and no
  number in this folder would show it.
- **Nothing about hidden glasses.** Every solution here reports only what some
  picture held. Recovering a glass no picture held is
  [a shared step of its own](../../docs/02-segment-glasses/hidden-glasses.md).

## Reproducing

```
cd .. && make floor                 # the floor, both families
pixi run python 01-rules-on-the-table/run.py --scenes 20
pixi run python 01-rules-on-the-table/run.py --scenes 20 --crowded
```

The same two lines for each of the other five, from the problem folder. The
fitted ones need their training step first; each README says which.
