# Solution 8 — the learned pipelines, retrained

*Learned. Problems 2 and 3 each chose a learned pipeline. Retrain both on
mixed tables and join them: TopNet finds the glasses, the Ranker chooses where
to look, SideNet measures the profile, the rules name the kind from SideNet's
profile, and the forward model plans the pushes. The finding and the pushing
carry over. The naming does not: the rules' waist test cannot be run on
SideNet's sixteen widths.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

[Solution 1](../programmed/01-join-them-as-they-are.md) joins the programmed pieces. This one
joins the learned pieces, because those are the ones problems 2 and 3 took
forward. The question is the same: what holds when the kinds are mixed, and
what breaks.

## The pieces

| Piece | From | What it does | Where the model sits |
| --- | --- | --- | --- |
| TopNet | [`02-segment-glasses/02-train-from-scratch`](../../../../02-segment-glasses/02-train-from-scratch/README.md) | each glass pixel in the overhead picture votes for the middle of its glass | decider, for finding |
| Ranker | `02-segment-glasses/02-train-from-scratch` | orders the places the geometry allows for a side view | ranker |
| SideNet | `02-segment-glasses/02-train-from-scratch` | reads the height and 16 widths from the side picture | decider, for measuring |
| the forward model | [`03-push-glasses-apart/04-a-world-model`](../../../../03-push-glasses-apart/04-a-world-model/README.md) | predicts what a push does to every glass | decider, for pushing, checked by looking again |

Then the rules: `classify()` names the kind from SideNet's profile, and
`find_grip()` chooses the grip from it.

## What carries over

**Finding.** TopNet was scored on problem 2's scenes, which cycle through the
four kinds, one kind per scene. It found all 250 glasses. A mixed scene is new
to it, and it would be retrained on mixed scenes. `make train` in
`02-segment-glasses/02-train-from-scratch` retrains all three of its models in about a minute. Nothing
about voting for a centre depends on the kind.

**Choosing the view.** The veto in front of the Ranker is geometry, and the
Ranker only orders what the veto allows. A wrong order costs a spoiled picture
and a second look. That does not change with the kind.

**Pushing.** The forward model is the part problem 3 chose, and the part that
most needs retraining. It is given the table's one kind as an input, the same
on every row, and each glass's foot. On a mixed table there is no one kind, and
for a glass not yet measured there is no foot. [Solution
9](09-plan-the-whole-table-with-the-push-model.md) is what retraining it for
problem 4 means.

## What breaks: naming from SideNet's profile

In problem 2, SideNet's profile only had to be good enough to measure: height
to within 5.4 mm at the median, widths to within 2.4 mm. [Problem 2's
results](../../../../02-segment-glasses/results/README.md) found it measures worse than the
silhouette. The silhouette is out by 0.8 mm in height at the median.

In problem 4 the profile also has to carry the **name**. And the name is asked
of the profile by a question — is there a narrowest point with wider glass on
both sides? — that is very sensitive to a single level being a little low.

### What sixteen levels can carry

First, with no error at all. Each generated glass's exact outline was cut down
to 16 evenly spaced levels and handed to `classify()`:

| Made as | named |
| --- | --- |
| straight | 200 straight |
| tapered | 158 tapered, 42 straight |
| stemmed | 200 stemmed |
| short-stemmed | 200 short-stemmed |

The same as the exact outline. Sixteen levels are enough, when they are
right.

### And with error in them

Then with error added: every width moved by its own random amount, and the
height by 3%. This is harsher than SideNet, whose errors from level to level
are probably smooth rather than independent, so it is an upper bound on the
damage, not a prediction of it.

| width error, spread | straight named right | stemmed named right | stemmed named short-stemmed |
| --- | --- | --- | --- |
| 1.0 mm | 80 of 200 | 117 of 200 | 83 |
| 2.4 mm | 45 of 200 | 117 of 200 | 81 |
| 4.0 mm | 33 of 200 | 134 of 200 | 60 |

At a spread of 1 mm — less than half of SideNet's median width error — 120 of
200 straight glasses get a waist, and 83 of 200 stemmed glasses are named
short-stemmed. That last one is the wrong-but-plausible name [solution
1](../programmed/01-join-them-as-they-are.md#the-name-can-be-wrong-where-nothing-checks-it)
found: same grip, 20 N instead of 6.

### Why

On a straight wall, the 16 widths are nearly equal. One of them read a
millimetre low has wider glass above it and below it, and that is exactly what
`waist_at()` calls a waist. The silhouette does not do this, because it has
hundreds of rows and smooths each over five, so one wandering row cannot make a
waist.

On a stemmed glass, the waist's height decides between stemmed and
short-stemmed. At 16 levels the waist can only be at one of 16 heights, a step
of 0.0625 of the glass. The nearest grippable stemmed glass has its waist 0.045
from the line. One step is larger than that margin.

A short-stemmed glass's stem is 0.154 to 0.171 of its height, which is two or
three of the sixteen levels. [Solution
2](../programmed/02-a-name-that-shows-its-evidence.md)'s stem-length rule would ask for two
levels, and one misread level would then decide it.

## The verdict

**Keep the finding and the pushing. Do not measure with SideNet.** Measure with
the silhouette, as problem 2's programmed twin does, because the name needs a
profile with enough rows to smooth. [Problem 2's
results](../../../../02-segment-glasses/results/README.md#what-the-comparison-says) already
said the silhouette measures better. Problem 4 turns that from "more accurate"
into "the only one the naming can use".

That is what the recommended combination does.

## What it needs

- `02-segment-glasses/02-train-from-scratch` retrained on mixed scenes: a minute.
- The forward model retrained on mixed tables: see [solution
  9](09-plan-the-whole-table-with-the-push-model.md).
- A mixed-kind bench to score it on, the same as every problem 4 solution.

## Where it is strong and where it breaks

**Strong.** The finding and the pushing are the pieces the two problems
measured and chose. Both carry over with retraining and nothing else.

**Breaks.**

- **SideNet's profile cannot carry the name.** Measured above, with a harsh
  error model; the direction is not in doubt even if the size is.
- **Retraining is not free.** Each learned piece has to be retrained whenever
  the mix of kinds changes, and each one's weights file has to be kept in step
  with the cell.
- **The learned finding was scored on opaque glasses with a perfect depth
  camera**, as problem 2 says. That does not change with the kinds.

## Where the idea comes from

**Carrying a decision's uncertainty into the next step.** SideNet's errors were
acceptable as a measurement and are not as the input to a threshold. A
threshold turns a small error near the line into a whole wrong answer. That
is why a measurement that feeds a decision has to be judged by the decision,
not by its own error.

**Feature detection needs sampling finer than the feature.** A waist found on
16 samples is a waist a sample wide. The same reason edge detectors smooth
before they differentiate.

## Where it sits among the other solutions

It is the learned counterpart of [solution 1](../programmed/01-join-them-as-they-are.md).
Its finding piece is interchangeable with problem 2's clustering. Its pushing
piece becomes [solution 9](09-plan-the-whole-table-with-the-push-model.md). Its
measuring piece is replaced by the silhouette in the recommended combination.

← [Solution 7 — guess the kind from above](07-guess-the-kind-from-above.md) · [Solution 9 — plan the whole table with the push model](09-plan-the-whole-table-with-the-push-model.md) →
