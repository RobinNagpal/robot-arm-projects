# Problem 3 — geometry generates, a model ranks

Plain geometry lists every legal push. A fitted model puts them in order, and
the arm makes the first push. The model can never add a push or bring back a
refused one. So a wrong answer costs one wasted push and nothing worse.

This is solution 2 of [the six](../docs/solutions/overview.md).
[Geometry generates, a model
ranks](../docs/solutions/02-geometry-ranked.md) gives
the reasoning. This file says what was built, how to run it, and what it
measured.

## The measurement comes first, and it decides the rest

A ranker has nothing to learn from a group of tied candidates. So the spread
of the label inside each group is measured before fitting. `spread.py` does
this and writes `spread.json`: **60 training tables, 4,511 candidate pushes
really made, 106 seconds.** The table gives how much the room gained varies
from best to worst inside one glass's candidates.

| Within one glass's candidates | Room gained, best to worst |
|---|---|
| the pushes that finish the job | **0.000 mm** median, 0.144 mm mean, over 161 groups |
| the pushes that only ease the crowding | 11.9 mm median, 14.5 mm mean, over 212 groups |
| the same push made four times | 0.000 mm by the simulator's record, 4.9 mm as the camera measures it |

The job-finishing pushes tie exactly. `nudge.along` stops each heading at the
first travel that gives the glass room. So they all land within **0.96 mm** of
the same room margin. The
[document](../docs/solutions/02-geometry-ranked.md#what-the-geometry-proposes)
explains why. The test
`test_each_heading_stops_at_the_first_travel_that_works` checks it in code.

So the order can matter in only two places: among pushes that only ease the
crowding, and in which glass to push next. For one glass, the printed rule
already matches the best candidate in **159 of 206** groups. The best choice
beats it by 0.0 mm at the median. Across a whole table the gap is small:
2.56 mm of room at the median. The rule's own choice toppled a glass in 1 of
82 decisions.

## What it scores, against the same geometry without the model

Both columns are the same loop over the same 50 held-out tables, with the
same budget and the same candidates. Only the chooser differs. The right-hand
column matches solution 1's own `results.json` number for number. That checks
that this folder lists the same candidates as that one.

| | Ranked (`results.json`) | Printed rule (`rule.json`) |
|---|---|---|
| Tables done | **14** | **14** |
| Tables wrong | 1 | 1 |
| Glasses racked | **107** of 251 | **107** of 251 |
| Glasses refused | 143 | 143 |
| Glasses toppled | 1 | 1 |
| Pushes | 182 (71 repeats) | **173** (63 repeats) |
| Travel against the floor | 1.32x | **0.87x** |
| Landing, median / worst | **1.6 / 32.8 mm** | 1.7 / 57.6 mm |
| Thinking per push | 102 ms | **98 ms** |

**The ranker loses.** It ends exactly where the printed rule ends: the same
fourteen tables, the same 107 glasses, the same single topple. But it spends
nine more pushes and **half again as much travel**.

With the real Robotiq 2F-85, most refusals happen before any choosing. 53 are
the hand too wide to get behind a glass. 87 are it too tall to push one safely.
Ordering cannot change either. The model's top input is now **push height over
the topple limit**, at 0.43 of its importance.

The ranker takes the longer route because of its label. It learns **room
gained**, but the run is scored on **glasses that end up grippable**. In
`training.json`, its top pick finishes the job in **47 of the 83 decisions that
offer one**. The rule does every time. By its own label the ranker is better:
it gives up 4.4 mm of room against the best candidate, where the rule gives up
18.7 mm. It still clears no more tables. So keep the simpler one. [Where it is
strong and where it
breaks](../docs/solutions/02-geometry-ranked.md#where-it-is-strong-and-where-it-breaks)
has the full argument.

## How it works

```
1. look ──▶ rack every glass with room
2. tipping: safe, refused, or settle it with a 5 mm push and a look
3. geometry enumerates every legal push ──▶ model scores each ──▶ sort
4. make the first push ──▶ look again ──▶ back to 1
   no candidate anywhere ──▶ refuse the rest, with the reason
```

Everything before the sort is arithmetic, and so is every refusal. The model
acts at the sort and nowhere else.

**The eight inputs** are in one function in `features.py`. [The
document](../docs/solutions/02-geometry-ranked.md#the-inputs-are-lengths-counts-and-ratios)
lists them and explains why none is a position on the table.

What the fit says mattered, in order: the topple ratio (0.43), the foot width
(0.38), then the five geometric ones, with the push distance last (0.01). The
model mostly learned *which glass is risky to push*, not *which push is good*.

**The model** is 200 boosted regression trees of depth 3. It is fitted
pointwise on 4,844 labelled candidates from 190 training tables. The label is
the room the whole table gained, read from the simulator's record. A toppled
glass sets it to −1 m, so that push sorts below everything. 57 candidates
toppled a glass. The geometry passed them because its friction is a guess.

## Demonstrations, which is what this solution is for

Solutions 3 and 6 learn from this one's pushes. `demos.py` writes them to
`demonstrations/demos.jsonl`, one JSON object per line, in the order things
happened. The full field list is in that file's docstring. The shape is:

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

Units are metres and radians, except `room_gained_mm`. The observation is
exactly what `look()` returned, with problem 2's measurement error. The action
is given in both forms the bench accepts. One is the parameterised push. The
other is `waypoints`, the path the jaw really followed, which `follow()` takes
back. So a policy that emits waypoints trains on the same demonstrations as one
that emits push parameters. A table's number redraws that table exactly. A
consumer that needs pictures renders its own with `bench/top_view.py`.

`make demos` over the first 200 training tables gives **896 pushes on 200
tables**, 381 of them 5 mm test pushes. It takes 52 seconds and about 6 MB. 152
tables are done, 46 incomplete and 2 wrong, with 171 glasses refused and every
reason kept. Two pushes left a glass down. Both stay in the file with
`"toppled": true`.

Keep the refusals and the failures when training on this file. [It is the
teacher](../docs/solutions/02-geometry-ranked.md#it-is-the-teacher)
explains why dropping them biases the training.

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
about 5 minutes making pushes and **0.9 seconds** fitting the trees on a laptop
processor. `data/rows.npz` is cached, so refitting takes seconds. At run time
the ranker spends 102 ms per push, as in the table above. Most of that is the
enumeration, not the trees: the printed rule, which scores nothing, spends
98 ms. Timings on a busy machine read roughly twice as much.

`data/`, `model/`, `demonstrations/` and `videos/` are not in git. Each is
regenerated from a list of table numbers. Any run shorter than the 50 held-out
tables writes `partial.json`, never `results.json`.

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
| `measure_push_speed.py` | Whether a slower push topples less. It does not |
| `../bench/` | The tables, the physics and the scoring, shared by all six |

**The enumerator is imported, not copied.** `candidates.py` loads
`../01-one-fixed-nudge/plan.py` by file path and calls it `nudge`. So the
heading sweep, the stepped travel, the four tests, the tipping rule and the
shortfall have one definition in this repository. It is loaded by file, not
through `sys.path`, for two reasons. The folder's name starts with a digit, so
it is not a package. And a folder on the path brings its `run.py`, which
silently shadowed this folder's own. The only new enumeration code is the loop
that keeps all survivors instead of choosing one. A test checks that the
printed rule over them picks the same push solution 1 picks.

## What this does not cover

- **The push budget moved while this was written.** It now belongs to the
  bench: 4 per glass, 16 per table. Solution 1 used to spend 3 and 15. Both
  columns above use the shared budget. Solution 1 was re-run under it too, so
  its `results.json` and this folder's `rule.json` agree on every count.
  Earlier copies of either file cannot be compared with these.
- **The refusal wording differs from solution 1's.** Where no candidate
  survives, solution 1 reports "nowhere clear to push it to". This folder
  splits those glasses in two. Some had no candidate at all. Others had only
  candidates too slight to be worth making, reported as "still without room
  after pushing". The glasses are the same, grouped differently.
- **One friction, never measured.** The bench's private coefficients decided
  every label. A model fitted on them has learned what topples on this bench.
- **The fit is deterministic.** There is no subsampling, and every input is
  considered at each split. Training twice on the same rows gives the same
  trees, and the seed makes no difference. The run is deterministic too, so one
  run is a measurement.
- **It says nothing about the commonest refusal.** A ranking over an empty set
  is still empty. Glasses with nowhere clear to go are refused before the model
  is reached.
