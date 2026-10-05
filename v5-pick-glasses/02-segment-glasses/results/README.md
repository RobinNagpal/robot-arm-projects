# Problem 2 — the six solutions side by side

Six ways of turning the same pictures into the same masks, all scored on the
bench described in
[`docs/02-segment-glasses/the-bench.md`](../../docs/02-segment-glasses/the-bench.md):
the same 20 held-out arrangements from each family, the same three survey
stations per arrangement, the same shared arithmetic turning a mask into a place
and a width, and the same scorecard. None of them was trained or tuned on these
arrangements. Every number here comes from a folder's own `results.json`.

## The results

Each solution's own README explains its numbers; this page only sets them side
by side.

### Spawned layouts — 100 glasses, the spacing the cell's own layout rule gives

| | found | missed | merged | split | false | position median · worst | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 100 | 0 | 0 | 0 | 0 | 6.3 · 46.5 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | **100** | 0 | 0 | 0 | 0 | 6.3 · 46.5 mm | 98.9% | **0.0%** |
| [2 trained from scratch](../02-train-from-scratch/) | 63 | 37 | 0 | 0 | 0 | **0.5** · 19.1 mm | 98.2% | 1.5% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 10 | 90 | 0 | 0 | 0 | 28.1 · 36.3 mm | 100.0% | 4.3% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | 92 | 8 | 0 | 0 | 0 | 3.5 · 42.6 mm | **99.8%** | 4.4% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 76 | 24 | 0 | 0 | 0 | 2.6 · 43.1 mm | 96.9% | **0.0%** |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | 90 | 10 | 0 | 0 | 0 | 4.2 · 42.2 mm | 96.8% | **0.0%** |

### Crowded layouts — 101 glasses, closer than the layout rule allows

| | found | missed | merged | split | false | position median · worst | mask covered | mask not the glass |
|---|---|---|---|---|---|---|---|---|
| **floor** (exact masks) | 83 | 18 | 1 | 1 | 0 | 0.4 · 50.0 mm | 100.0% | 0.0% |
| [1 rules on the table](../01-rules-on-the-table/) | 28 | 73 | **21** | 1 | 0 | 18.6 · 129.7 mm | 99.9% | 54.7% |
| [2 trained from scratch](../02-train-from-scratch/) | 72 | 29 | 1 | 0 | 0 | 0.7 · 43.8 mm | 97.2% | 1.4% |
| [3 YOLO as it downloads](../03-yolo-zero-shot/) | 4 | 97 | 0 | 0 | 0 | 36.5 · 46.6 mm | 84.5% | 3.6% |
| [4 YOLO fine-tuned](../04-yolo-fine-tuned/) | 66 | 35 | 1 | 0 | 0 | **0.5** · 42.3 mm | **99.2%** | 3.7% |
| [5 SAM 2 with a keeper](../05-sam2-with-a-keeper/) | 71 | 30 | 0 | 0 | 0 | 0.9 · 28.7 mm | 98.4% | **0.0%** |
| [6 RF-DETR fine-tuned](../06-rf-detr-fine-tuned/) | **74** | 27 | 2 | 1 | 0 | **0.5** · 58.4 mm | 97.4% | **0.0%** |

Solutions 5 and 6 have more than one rung; the rows above are rung `sam2` and
rung `modal`. The floor is `bench/floor.py` with the renderer's own masks, which
no segmenter can improve on. Even it misses 18 crowded glasses, because a glass
standing wholly behind another is in no picture at all.

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
Solution 1 finds every glass the layout spaces and merges 21 pairs the moment
they stand closer than the rule allows, because its one grouping distance is
what decides. Solution 2 merges almost nothing and misses 37 glasses on the easy
layouts, because a glass whose middle falls outside the picture casts votes that
land nowhere — a limit of the voting design rather than of its training.

**Borrowed weights carry the names, not the shapes.** Solution 3 finds 10 of
100 with nothing merged, split or false: it locates the objects and calls them
sports balls and frisbees. Continuing its training on this cell and cutting the
vocabulary to one class is solution 4, and the gap between the two — 10 found
against 92 — is the measurement of what that training bought.

**The two mask numbers disagree about who is best, and that is the useful
result.** Solution 1's masks almost never claim a pixel that is not glass
(0.0%), because a pixel reaches a mask only by standing above the table; the
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
