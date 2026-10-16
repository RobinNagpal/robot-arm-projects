# Solution 1 — rules on the table

Every pixel standing above the table becomes a point in the room. The points
are grouped by how far apart they stand **on the table**, not in the picture.
The pixels that fed one group are that glass's mask. There is no model, no
weights file and no training data, so **not one number in this folder was
fitted to anything**. The reasoning is in
[`docs/02-segment-glasses/solutions/01-rules-on-the-table.md`](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md).
The bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

## The files

- `find.py` — the grouping, the circle fitted to each group, and the split of
  a group too wide to be one glass. It answers the same
  `Finder.find(picture, kind)` interface as the other five solutions. It hands
  back a boolean mask per glass. The place and the width come from the bench's
  `masks_to_glasses`.
- `run.py` — runs the held-out scenes over the survey's three stations and
  scores them. It writes `results.json` and `results-crowded.json`.
- `test_programmed.py` — the quick checks. No weights, no network.
- `views.py`, `measure.py` — **not part of this problem.** The bench stops at
  a mask, a place and a width. Choosing a viewpoint and measuring from the side
  come after that. They are kept here because
  [problem 5's documents](../../docs/problem-5/solutions/solution-overview.md)
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

Only arithmetic: no labels, no training run, no graphics card. A 20-scene run
over three stations each (60 pictures) takes about 7 seconds, including the
rendering.

## Results — 20 held-out scenes from each family, three stations each

The table gives one column per family of arrangements.

| | spawned | crowded |
|---|---|---|
| glasses put out | 100 | 101 |
| **found** | **100** | **71** |
| missed | 0 | 30 |
| merged / split / false | 0 / 0 / 0 | 10 / 1 / 0 |
| position error, median · worst | 8.5 · 46.5 mm | 6.0 · 58.2 mm |
| mask covered, median · worst | 98.9% · 24.9% | 94.6% · 1.2% |
| mask not the glass, median · worst | 0.0% · 0.0% | 0.0% · 79.3% |
| doubted: too wide, and it did not come apart | 0 | 3 |

**On spawned layouts every glass is found, none is merged and nothing is
handed over.** The bench's floor finds 100 of 100 at 6.3 mm median and 46.5 mm
worst. So the median place is 2.2 mm behind the floor, and the worst error is
the floor's own. Those 2.2 mm are the whole cost of the width check here. Of
289 groups, 285 are one glass on the first fit and 4 are cut in two. The parts
of those four each report one real glass, and the bench's
one-report-per-place step collapses them. The layout rule keeps every glass
150 mm from the next, so a split has nothing to do on these layouts.

**The mask numbers come out as the bench predicts, in both directions.** The
next table gives the spawned run's mask numbers for each kind.

| kind | covered | not the glass |
|---|---|---|
| straight glass | 99.5% | 0.0% |
| tapered glass | 100.0% | 0.0% |
| stemmed glass | 86.6% | 0.0% |
| short stemmed glass | 88.7% | 0.0% |

The two kinds without a stem are covered almost completely. The two with a
stem are 11–13 points behind. So for a written rule the stem really is the hard
part. The mask almost never claims a pixel that is not the glass: 0.0% median
and 0.0% worst. [The masks are what this
contributes](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md#the-masks-are-what-this-contributes)
explains why.

**On crowded layouts the width check recovers the glasses that the grouping
distance ran together, and repeating it makes it enough.** The next table
compares three versions of the rule on the same 20 arrangements, with the
floor beside them.

| crowded, 101 glasses | no width check | one split only | the split repeated | the floor |
|---|---|---|---|---|
| found | 28 | 17 | **71** | 83 |
| missed | 73 | 84 | 30 | 18 |
| merged | **21** | 0 | 10 | 1 |
| split | 1 | 0 | 1 | 1 |
| position error, median · worst | 18.6 · 129.7 mm | 0.7 · 24.0 mm | 6.0 · 58.2 mm | 0.4 · 50.0 mm |
| mask not the glass, median | 54.7% | 0.0% | 0.0% | — |
| doubted | 0 | 54 | 3 | 0 |

**Without the check** the grouping distance decides everything. 73 glasses are
missed. 21 reports each quietly cover two glasses, with a median place 18.6 mm
out.

**With one split only** nothing is merged, and what is reported is almost
exact. But only 17 glasses are reported, and 54 groups are handed over. Over
the 60 crowded pictures, 72 groups held more than one glass and 47 held three
or more. [Why one split is not
enough](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md#why-one-split-is-not-enough)
explains the cause.

**With the split repeated** the rule finds 73.0 glasses per 100, against the
86.4 any method could find, averaged over five blocks. It hands a few groups
over. The price is 10.7 merged reports per 100, and a worse place: 8.7 mm at
the middle glass against the floor's 0.4 mm. A cut drawn where the dots divide
is not where the glasses divide. 69 groups came apart on this run, into 2 to 9
parts each. The parts often outnumber the glasses in the group. The bench's
one-report-per-place step absorbs most of that, which is why 10 reports are
merged rather than 30.

The second mask number agrees. It is 0.0% at the median, because a report on a
glass is still made of pixels that stood above the table. It is 79.3% at the
worst: one part of a cut group whose dots mostly belonged to its neighbour.

## What this does not do

- **No residual.** The document names a third number from the circle fit: how
  far a group's dots sit from the circle on average. None of its four outcomes
  uses it, so nothing here computes it.
- **No agreement between stations.** The document says a group only one
  station found should be reported as doubtful. But a solution here sees one
  picture at a time, and the bench joins the stations afterwards. So there is
  nowhere in this file to make that check.
- **No count of how many glasses a group holds.** Splitting stops when every
  part has an allowed width, not when the number of parts is right. So a group
  can come apart into more parts than it holds glasses. The bench's one report
  per place keeps that honest. The cost shows in the merged and split columns
  above.
- **No completion of hidden parts.** A glass no picture held leaves no trace
  here. The cure is outside this solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
