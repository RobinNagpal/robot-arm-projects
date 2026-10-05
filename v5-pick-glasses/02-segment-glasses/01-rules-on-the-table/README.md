# Solution 1 — rules on the table

Every pixel standing above the table becomes a point in the room, the points
are grouped by how far apart they stand **on the table** rather than in the
picture, and the pixels that fed one group are that glass's mask. There is no
model, no weights file and no training data, so **not one number in this folder
was fitted to anything**. Its document is
[`docs/02-segment-glasses/solutions/01-rules-on-the-table.md`](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md),
and the bench it is scored on is
[`docs/02-segment-glasses/the-bench.md`](../../docs/02-segment-glasses/the-bench.md).

## The files

- `find.py` — the grouping, the circle fitted to each group, the split of a
  group too wide to be one glass, and the same `Finder.find(picture, kind)`
  interface the other five solutions answer. It hands back a boolean mask per
  glass; the place and the width come from the bench's `masks_to_glasses`.
- `run.py` — the held-out scenes over the survey's three stations, scored;
  writes `results.json` and `results-crowded.json`.
- `test_programmed.py` — the quick checks. No weights, no network.
- `views.py`, `measure.py` — **not part of this problem.** The bench stops at a
  mask, a place and a width; choosing a viewpoint and measuring the glass from
  the side are the steps after that. They are kept here because
  [problem 4's documents](../../docs/problem-4/solutions/solution-overview.md)
  name `views.py` as the view check their pipeline uses. Nothing in `run.py`
  calls them.

## Running it

```
pixi run python 01-rules-on-the-table/run.py --scenes 20
pixi run python 01-rules-on-the-table/run.py --scenes 20 --crowded
pixi run pytest -q 01-rules-on-the-table
```

There is no train step, and nothing to download.

## What it costs

Nothing but arithmetic: no labels, no training run, no graphics card. A
20-scene run over three stations each — 60 pictures — takes about 7 seconds
including the rendering.

## Results — 20 held-out scenes from each family, three stations each

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **100** | **17** |
| missed | 0 | 84 |
| merged / split / false | 0 / 0 / 0 | 0 / 0 / 0 |
| position error, median · worst | 8.5 · 46.5 mm | 0.7 · 24.0 mm |
| mask covered, median · worst | 98.9% · 24.9% | 98.6% · 56.8% |
| mask not the glass, median · worst | 0.0% · 0.0% | 0.0% · 0.5% |
| doubted: too wide, and it did not come apart | 3 | 54 |

**On spawned layouts every glass is found and none is merged.** The place is
2.2 mm behind the bench's floor at the median — the floor finds 100 of 100 at
6.3 mm median and 46.5 mm worst — and those 2.2 mm are the whole cost of the
three refusals in the last row: reporting those groups instead of refusing them
puts the median back on 6.3 mm exactly. The three are two glasses, each drawn at
the very top of its kind's range and each refused by a fitted circle 0.2 to
0.4 mm over the kind's own ceiling. Both were reported from another station, so
nothing was lost but the best-placed sighting of them. The worst error is the
floor's own.

**The mask numbers come out as the bench predicts, in both directions.**

| kind | covered | not the glass |
|---|---|---|
| straight glass | 99.5% | 0.0% |
| tapered glass | 100.0% | 0.0% |
| stemmed glass | 86.6% | 0.0% |
| short stemmed glass | 88.7% | 0.0% |

The two kinds without a stem are covered almost completely and the two with one
are 11–13 points behind, so for a written rule the stem really is the hard part.
And the mask almost never claims a pixel that is not the glass — 0.0% median
and 0.0% worst — because a pixel reaches the wrong mask only if its dot chained
into the wrong group across a strip of bare table. Every pixel in every mask
carried a real depth reading, so nothing here is asserted and the bench has
nothing to exclude.

**On crowded layouts the width check turns a quiet failure into a loud one, and
that costs reports.** Before the check was built this solution found 28 of 101
with **21 of those reports covering two glasses at once**, a median place 18.6 mm
out and 129.7 mm at worst, and 54.7% of a merged mask belonging to some other
glass. With the check built it finds 17, **merges nothing at all**, places what
it does report to 0.7 mm at the median and 24.0 mm at worst, and 0.0% of a mask
is not the glass it was credited to. Eleven reports were traded away and
twenty-one merges went with them, and what is reported is now essentially
exact.

| crowded, 101 glasses | before the width check | after it | the bench's floor |
|---|---|---|---|
| found | 28 | **17** | 83 |
| merged | 21 | **0** | 1 |
| position error, median · worst | 18.6 · 129.7 mm | **0.7 · 24.0 mm** | 0.4 · 50.0 mm |
| mask not the glass, median | 54.7% | **0.0%** | — |
| doubted | 0 | 54 | 0 |

**The 54 refusals are the method's own honest edge, and they are countable.**
Over the 60 crowded pictures, 72 groups held more than one glass. 18 of them
came apart into two glasses, 17 of those holding exactly two. The other 54 were
handed over, and **47 of the 54 held three glasses or more** — 232 glass
sightings in all. The document says why a split in two cannot answer those: with
three glasses in a row two circles cannot say how many there are, only that
there are too many. The bench's crowded family stands three glasses to a line
and two lines to a scene, so that is most of what it draws.

## What this does not do

- **No residual.** The document names a third number from the circle fit — how
  far a group's dots sit from the fitted circle on average — as a measure of how
  well a circle explains a group. None of the four outcomes it prescribes uses
  it, so nothing here computes one.
- **No agreement between stations.** The document prescribes reporting as
  doubtful a group only one station found. A solution here is asked about one
  picture at a time and the stations are brought together by the bench
  afterwards, where a solution has no say, so there is nowhere in this file to
  make that check.
- **No split into more than two.** A group too wide for one glass is tried as
  two and handed over if that fails, which is what the document prescribes and
  what the crowded column above costs. **How much it costs was measured**, by
  splitting a half that is still too wide again instead of handing it over, up
  to four times: on the crowded scenes that finds 71 of 101 rather than 17, with
  10 merged reports rather than 0, a place 6.0 mm out at the median and 58.2 mm
  at worst, and 3 groups left over; on the spawned scenes it changes the counts
  not at all and removes the three refusals. That is a different rule from the
  one the document states, so it is written here as a measurement and not as
  code: the document would have to say it first.
- **No completion of hidden parts.** A glass no picture held leaves no trace
  here. The cure is outside this solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
