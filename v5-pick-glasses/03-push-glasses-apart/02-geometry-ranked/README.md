# Problem 3 — geometry generates, a model ranks

Plain geometry writes down every push that is legal. A fitted model puts the
survivors in order, and the arm makes the first push on the list. The model
can never add a push and never bring back one the geometry refused, so a wrong
answer costs one wasted push and nothing worse.

This is solution 2 of [the six](../../docs/03-push-glasses-apart/solutions/overview.md),
specified by [geometry generates, a model
ranks](../../docs/03-push-glasses-apart/solutions/02-geometry-ranked.md). Read that
for the reasoning; this file is what was built, how to run it, and what it
measured.

## The measurement comes first, and it decides the rest

The document says to measure the spread of the label inside a candidate group
before fitting anything, because a ranking over a group whose members are tied
has nothing to learn. Nobody had measured it. `spread.py` does, and the answer
is in `spread.json`: **60 training tables, 4,511 candidate pushes really made,
106 seconds.**

| Within one glass's candidates | Room gained, best to worst |
|---|---|
| the pushes that finish the job | **0.000 mm** median, 0.144 mm mean, over 161 groups |
| the pushes that only ease the crowding | 11.9 mm median, 14.5 mm mean, over 212 groups |
| the same push made four times | 0.000 mm by the simulator's record, 4.9 mm as the camera measures it |

The job-finishing pushes are an exact tie, and the reason is structural rather
than accidental: `nudge.along` stops each heading at the first travel that
gives the glass room, so every one of them lands on the same contour — within
**0.96 mm** of the same room margin, measured — and a table where every glass
has room has a shortfall of zero whichever push got it there. A test
(`test_each_heading_stops_at_the_first_travel_that_works`) proves the two
halves of that in code.

So the ordering can carry information in only two places: among the pushes
that merely ease the crowding, and across glasses, in which glass to push
next. For one glass, the printed rule is already as good as the best candidate
in **159 of 206** groups, and the best possible choice beats it by 0.0 mm at
the median. Across the whole table the gap is real but small: 2.56 mm of room
at the median, and the rule's own choice toppled a glass in 1 of 82 decisions.

## What it scores, against the same geometry without the model

Both columns are the same loop over the same 50 held-out tables with the same
budget and the same candidate set. The only difference is who picks. The
right-hand column is also, number for number, solution 1's own re-run
`results.json`, which is the check that this folder enumerates what that one
enumerates.

| | Ranked (`results.json`) | Printed rule (`rule.json`) |
|---|---|---|
| Tables done | 31 | **33** |
| Tables wrong | **0** | **0** |
| Glasses racked | 185 of 251 | **195** of 251 |
| Glasses refused | 66 | **56** |
| Glasses toppled | **0** | **0** |
| Pushes | 229 (109 repeats) | **213** (90 repeats) |
| Landing, median / worst | 1.0 / 3.9 mm | 1.0 / 3.9 mm |
| Thinking per push | 75 ms | **59 ms** |

**The ranker loses.** It racks ten fewer glasses for sixteen more pushes, and
the document predicted exactly this. It is not a matter of an unlucky fit:
three rankers fitted on bootstrap resamples of the same rows racked 180, 181
and 184 glasses on the same tables, so the gap to the rule's 195 is several
times the spread of the fitting.

The reason is visible in the validation numbers (`training.json`) and it
is worth stating, because it is a lesson about the label rather than about
boosted trees. The model is fitted on **room gained**, and the run is scored on
**glasses that end up grippable**. Those are not the same quantity. A push that
spreads 20 mm of room over three glasses scores higher than one that finishes
a glass outright, and only the second gets a glass off the table. On the
validation tables the ranker's top pick takes a job-finishing push in **47 of
the 83 decisions that offer one**; the printed rule takes it every time.

By its own label the ranker is the better chooser of the two — across a whole
decision it gives up 4.4 mm of room against the best candidate where the rule
gives up 18.7 mm — and it still clears fewer tables. That is the measurement
the document asked for, and it says keep the simpler one.

## How it works

```
1. look ──▶ rack every glass with room
2. tipping: safe, refused, or settle it with a 5 mm push and a look
3. geometry enumerates every legal push ──▶ model scores each ──▶ sort
4. make the first push ──▶ look again ──▶ back to 1
   no candidate anywhere ──▶ refuse the rest, with the reason
```

Everything before the sort is arithmetic, and so is every refusal. The model
enters at the sort and nowhere else.

**The eight inputs** (`features.py`, all of them in one function): the contact
angle relative to the line to the nearest neighbour's edge; the push distance;
the room the destination would have; the destination's distance to the zone
edge and to the rack; how many neighbours sit within reach, as a count; the
foot width; and the push height as a fraction of the topple limit at the worst
friction believed. Every one is a length, an angle, a count or a ratio, and
none is a position on the table: move the whole arrangement and only the two
distances to fixed features of the cell change.

What the fit says mattered, in order: the topple ratio (0.43), the foot width
(0.38), then the five geometric ones, with the push distance last (0.01). The
model mostly learned *which glass is risky to push*, not *which push is good* —
which is the same finding as the spread measurement, arrived at from the other
side.

**The model** is 200 boosted regression trees of depth 3, fitted pointwise on
4,844 labelled candidates from 190 training tables. The label is the clear room
the whole table gained, read from the simulator's record, with a toppled glass
set to −1 m so it sorts below everything. 57 of those candidates toppled a
glass: the geometry passed them because the friction in its limit is a guess,
and they are the rows that teach the model to stand further from the limit.

## Demonstrations, which is what this solution is for

Solutions 3 and 6 learn from this one's pushes. `demos.py` writes them to
`demonstrations/demos.jsonl`, one JSON object per line, in the order things
happened. The full field list is in that file's docstring; the shape is:

```json
{"record": "push", "table": 0, "step": 0, "kind": "straight_glass",
 "observation": [{"id": 3, "x": 0.58, "y": -0.19, "height": 0.16,
                  "widest": 0.063, "foot": 0.071, "standing": true}],
 "action": {"glass": 3, "start": [0.54, -0.17], "heading": 5.93,
            "reach": 0.071, "travel": 0.064, "aim": [0.64, -0.21]},
 "waypoints": [[0.5409, -0.17317, 0.3, 5.93412], ["...147 of them..."]],
 "probe": false,
 "felt": {"blocked": false, "touched": 0.006, "jammed": false,
          "peak": 1.74, "pushed": 0.064},
 "room_gained_mm": 55.25, "toppled": false}
{"record": "table", "table": 0, "kind": "straight_glass", "glasses": 4,
 "pushes": 1, "racked": 4, "outcome": "done", "refused": {}}
```

Metres and radians throughout, except `room_gained_mm`. The observation is
exactly what `look()` returned, carrying problem 2's measurement error. The
action is given twice, in both forms the bench accepts: as the parameterised
push, and as `waypoints`, the path the jaw really followed, which the bench
samples on every action and `follow()` takes back. So a policy that emits
waypoints is trained on the same demonstrations as one that emits push
parameters. A table's number redraws that table exactly, so a consumer that
needs pictures renders its own with `bench/top_view.py`, and nothing is
archived that can be regenerated.

`make demos` over the first 200 training tables gives **896 pushes on 200
tables** (381 of them 5 mm test pushes) in 52 seconds and about 6 MB: 152
tables done, 46 incomplete, 2 wrong, with 171 glasses refused and every reason
kept. Two pushes left a glass down, and both are in the file with
`"toppled": true` rather than removed.

Two things to carry into training on it. A **refusal is a result**: a table
with a non-empty `refused` is a correct answer, and dropping those tables
removes the situations this teacher found hard. And **filtering to the pushes
that worked biases which tables are covered**, not only which actions, so every
push's outcome is recorded rather than the failures being dropped here.

## Running it

```
make help
make spread      # the measurement above, about 2 minutes; writes spread.json
make train       # label 200 tables and fit, about 5 minutes; writes model/ and training.json
make run         # the 50 held-out tables; writes results.json
make rule        # the same with the model deleted; writes rule.json
make demos       # demonstrations for solutions 3 and 6
make test        # the quick checks; no trained model needed
```

Nothing here needs an accelerator and nothing downloads. `make train` spends
about 5 minutes making pushes and **1.7 seconds** fitting the trees on a laptop
processor; `data/rows.npz` is cached, so refitting is seconds. Run time is a
few hundred threshold comparisons per candidate, which is the 75 ms per push
above, and most of that is the enumeration rather than the trees: the printed
rule, which scores nothing, spends 59 ms. Both figures were taken on an idle
machine, because the same runs timed while the machine was busy read roughly
twice as much.

`data/`, `model/`, `demonstrations/` and `videos/` are not in git, because each
is regenerated from a list of table numbers. Any run shorter than the 50
held-out tables writes `partial.json`, never `results.json`.

## Where the code is

| File | What it does |
|---|---|
| `candidates.py` | Every legal push, kept as a set. Loads solution 1's `plan.py` |
| `features.py` | The eight inputs, in one function |
| `rollout.py` | Make one candidate on the bench and label it |
| `ranker.py` | The trees, and the sort they are used for |
| `train.py` | Collect, label, fit, validate, save |
| `spread.py` | The measurement above |
| `run.py` | The loop over the held-out tables, with `--rule` for the ablation |
| `demos.py` | Demonstrations for solutions 3 and 6 |
| `../bench/` | The tables, the physics and the scoring, shared by all six |

**The enumerator is imported, not copied.** `candidates.py` loads
`../01-one-fixed-nudge/plan.py` by file path and calls it `nudge`, so the
heading sweep, the stepped travel, the four tests, the tipping rule and the
shortfall arithmetic have exactly one definition in this repository. It is
loaded by file rather than by putting that folder on `sys.path`, because that
folder's name starts with a digit — so it is not a package — and because a
folder on the path brings its `run.py` with it, which silently shadowed this
folder's own. The only enumeration code written here is the loop that keeps
the survivors instead of choosing among them; a test checks that the printed
rule over those survivors picks the same push solution 1 picks.

## What this does not cover

- **The push budget moved while this was written.** It now belongs to the
  bench — 4 per glass, 16 per table — where solution 1 used to spend 3 and 15.
  Both columns above were run under the shared budget, and solution 1 has since
  been re-run under it too, which is why its `results.json` and this folder's
  `rule.json` agree on every count. Earlier copies of either file are not
  comparable with these.
- **The refusal wording differs from solution 1's.** Where no candidate
  survives anywhere, solution 1 reports every remaining glass as "nowhere clear
  to push it to"; this folder separates the glasses that had no candidate at all
  from those whose candidates were all too slight to be worth making, which it
  reports as "still without room after pushing". The counts are the same
  glasses, grouped differently.
- **One friction, never measured.** Every label here was decided by the
  bench's private coefficients. A model fitted on them has learned what topples
  on this bench.
- **The fit is deterministic**, with no subsampling and every input considered
  at each split, so training twice on the same rows gives the same trees and a
  seed makes no difference. The spread quoted above therefore comes from
  resampling the rows, which is the only variation this method has. The run
  itself is deterministic too, so one run of it is a measurement.
- **It says nothing about the commonest refusal.** A ranking over an empty set
  is still empty, and glasses with nowhere clear to go are refused before the
  model is reached.
