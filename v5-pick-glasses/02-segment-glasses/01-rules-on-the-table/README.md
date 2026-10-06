# Solution 1 — rules on the table

Every pixel standing above the table becomes a point in the room, the points
are grouped by how far apart they stand **on the table** rather than in the
picture, and the pixels that fed one group are that glass's mask. There is no
model, no weights file and no training data, so **not one number in this folder
was fitted to anything**. Its document is
[`docs/02-segment-glasses/solutions/01-rules-on-the-table.md`](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md),
and the bench it is scored on is
[`docs/02-segment-glasses/the-examiner.md`](../../docs/02-segment-glasses/the-examiner.md).

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
| **found** | **100** | **71** |
| missed | 0 | 30 |
| merged / split / false | 0 / 0 / 0 | 10 / 1 / 0 |
| position error, median · worst | 8.5 · 46.5 mm | 6.0 · 58.2 mm |
| mask covered, median · worst | 98.9% · 24.9% | 94.6% · 1.2% |
| mask not the glass, median · worst | 0.0% · 0.0% | 0.0% · 79.3% |
| doubted: too wide, and it did not come apart | 0 | 3 |

**On spawned layouts every glass is found, none is merged and nothing is handed
over.** The place is 2.2 mm behind the bench's floor at the median — the floor
finds 100 of 100 at 6.3 mm median and 46.5 mm worst — and the worst error is the
floor's own. Those 2.2 mm are the width check's whole cost here: of 289 groups,
285 are one glass on the first fit and 4 are cut in two, and the parts of those
four are reports of one real glass each, which the bench's one-report-per-place
step then collapses. The layout rule keeps every glass 150 mm from the next, so
there is nothing on these layouts for a split to do.

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

**On crowded layouts the width check is what recovers the glasses the grouping
distance ran together**, and repeating it is what makes it enough. Three numbers
for the same 20 arrangements, because the two intermediate states are both worth
seeing:

| crowded, 101 glasses | no width check | one split only | the split repeated | the floor |
|---|---|---|---|---|
| found | 28 | 17 | **71** | 83 |
| missed | 73 | 84 | 30 | 18 |
| merged | **21** | 0 | 10 | 1 |
| split | 1 | 0 | 1 | 1 |
| position error, median · worst | 18.6 · 129.7 mm | 0.7 · 24.0 mm | 6.0 · 58.2 mm | 0.4 · 50.0 mm |
| mask not the glass, median | 54.7% | 0.0% | 0.0% | — |
| doubted | 0 | 54 | 3 | 0 |

**Without the check** the grouping distance decides everything: 73 glasses are
missed and 21 reports each cover two glasses at once, quietly, with a median
place 18.6 mm out.

**With one split and no repetition** nothing is merged and what is reported is
almost exact, but only 17 glasses are reported at all and 54 groups are handed
over. The reason is the arrangements rather than the rule: over the 60 crowded
pictures, 72 groups held more than one glass and 47 of those held three or more,
and one split into two necessarily leaves a part still holding two.

**With the split repeated** the same rule asked again of a part still too wide
finds 71 of the 83 that any method could find, and hands 3 groups over — 15
glass sightings in all. The 10 merged reports are the price, and so is the
place: 6.0 mm at the median against 0.7 mm, because a cut drawn where the dots
happen to divide is not where the glasses divide. 69 groups came apart on this
run, into 2 to 9 parts each. The parts are often more numerous than the glasses
in the group, and the bench's one-report-per-place step absorbs most of that,
which is why 10 reports are merged rather than 30.

The second mask number says the same thing from the other side: 0.0% at the
median, because a report that lands on a glass is still made of pixels that
stood above the table, and 79.3% at the worst, which is one part of a cut
group whose dots mostly belonged to its neighbour.

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
- **No count of how many glasses a group holds.** The splitting stops when
  every part is a width the kind allows, not when the number of parts is right,
  so a group can come apart into more parts than it holds glasses. What keeps
  that honest is the bench's one report per place, and what it costs is in the
  merged and split columns above.
- **No completion of hidden parts.** A glass no picture held leaves no trace
  here. The cure is outside this solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
