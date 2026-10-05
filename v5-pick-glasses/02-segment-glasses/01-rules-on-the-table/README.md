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

- `find.py` — the grouping, and the same `Finder.find(picture, kind)` interface
  the other five solutions answer. It hands back a boolean mask per glass; the
  place and the width come from the bench's `masks_to_glasses`.
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
| **found** | **100** | **28** |
| missed | 0 | 73 |
| merged / split / false | 0 / 0 / 0 | 21 / 1 / 0 |
| position error, median · worst | 6.3 · 46.5 mm | 18.6 · 129.7 mm |
| mask covered, median · worst | 98.9% · 24.9% | 99.9% · 86.4% |
| mask not the glass, median · worst | 0.0% · 0.0% | 54.7% · 77.4% |

**On spawned layouts it sits exactly on the bench's floor.** The floor — the
same arithmetic on the masks the renderer itself drew — finds 100 of 100 at
6.3 mm median and 46.5 mm worst, and those are this solution's numbers to the
millimetre. The place has nothing left to gain here: what remains is the
arithmetic's own error, not the rule's. That is the saturation
[the bench document](../../docs/02-segment-glasses/the-bench.md) warns about,
and it is why the mask numbers below matter more than the places.

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

**On crowded layouts the one setting runs out, and it runs out loudly.** 73 of
101 glasses are missed and 21 reports cover two glasses at once. The cause is
the grouping distance: it closes gaps of up to 25 mm inside one glass, and the
crowded family stands glasses closer than the layout rule allows, so two
glasses whose dots come within that distance are one group and one report. The
bench's floor on the same scenes finds 83 of 101, so most of this gap is the
rule and not the view. The merged masks also show up in the second mask number
— 54.7% of a merged mask is not the glass it was credited to, against 0.0% on
spawned layouts — which is exactly the leak the bench says that number catches.

## What this does not do

- **No width check, and the document asks for one.** The document prescribes
  fitting a circle to each group, splitting a group too wide for the kind into
  two with k-means, and reporting as doubtful what still fails. **None of that
  is built.** A refusal without the split was tried and measured, and it is
  worse than nothing: the bench's own exact masks, judged one station at a time,
  give a footprint outside the kind's range for 66 of 297 glass sightings,
  because a glass clipped at the edge of one station's frame shows only part of
  its footprint. The station that saw a glass squarely is chosen by the bench
  afterwards, where a solution has no say, so the check belongs after the survey
  rather than inside one picture. Building the split is what would repair the
  crowded column above.
- **No completion of hidden parts.** A glass no picture held leaves no trace
  here. The cure is outside this solution, in
  [looking again at what was hidden](../../docs/02-segment-glasses/hidden-glasses.md).
- **Not Gazebo.** The pictures come from `../bench/render.py`, which uses the
  wrist camera's lens but not the simulator.
