# Problem 3 — the programmed way

Some glasses stand too close together for the gripper to get round them. The
arm pushes them apart across the table, then picks them up. Everything here is
geometry and simple physics: no training, no model.

It holds the candidate geometry that [one fixed
nudge](../docs/solutions/01-one-fixed-nudge.md) and
[geometry generates, a model
ranks](../docs/solutions/02-geometry-ranked.md) both use.
The reasoning is in those two pages. This file says what the code does, how to
run it, and what it measured. Two changes are explained at the end.

## Words used below

- **Room.** A glass has room when every other glass's edge is at least 76 mm
  from its middle. That is the space the open gripper needs. [The
  problem](../docs/problem.md#the-gap-that-matters-is-not-the-gap-between-the-glasses)
  explains it.
- **Take.** Pick a glass up and put it in the rack. Problem 1 does the real
  pick; here the glass is just lifted off the table.
- **Jaw.** The closed gripper, held level. It pushes with its fingertips. Its
  top edge is 107 mm above the table.

## The loop

The arm repeats these steps until the table is empty or nothing more can be
done.

**1. Look.** Get each glass's position, height, widest width and foot width
from the camera. If any glass has fallen over, stop.

**2. Take every glass that has room.** Each glass taken leaves more space for
the others, so sometimes no pushing is needed at all. Then look again.

**3. Check each glass can be pushed without tipping over.** A glass slides if
it is pushed low enough, and tips if pushed too high. [Pushing without
toppling](../docs/pushing-without-toppling.md#the-limit-slide-or-tip)
explains the rule. The limit is

    push height < (half the foot width) / friction

The friction is not known, so the arm checks two values:

| Result | What happens |
|---|---|
| Slides even at high friction (0.5) | Safe to push. |
| Tips even at low friction (0.2) | Refused: "tips before it slides". |
| Slides only if friction is low | **Test push**: push it 5 mm and look again. If it moved, it slides, so push it. If it did not move, it leaned and fell back, so refuse it. |

The test push is only made if 5 mm cannot lean the glass far enough to fall.

**4. Find a safe push.** For each glass, try 72 directions and lengths up to
150 mm. A push is safe only if:

- the glass ends up inside the glass area;
- the arm can reach every point of the push;
- the glass does not move closer to any other glass on the way;
- the jaw clears every other glass, both coming down and while pushing.

**5. Choose the push.**

- First choice: the shortest safe push that gives a glass room.
- If there is none: the safe push that makes the table least crowded overall.
  It frees nothing yet, but the next push may.
- If there is no safe push at all: refuse the glasses that are left, with the
  reason "nowhere clear to push it to".

**6. Push.** The jaw comes down just outside the glass, moves forward slowly
until it feels the glass, pushes, backs off and lifts. Then go back to step 1
and look at where the glass really went. The arm never assumes the push went
as planned.

The push budget belongs to the bench. Every solution reads it from there, so
all six get the same number of tries.

## Where the code is

| File | What it does |
|---|---|
| `run.py` | The loop above, and the scoring run |
| `plan.py` | The tipping check, the test push, and the search for a safe push |
| `../03-push-glasses-apart/bench/` | The tables, the physics (MuJoCo) and the scoring, shared with `03-push-glasses-apart/04-a-world-model` |

## Running it

```
make run        # the 50 test tables; writes results.json
make film       # videos of the first 3 test tables, in videos/
make test
```

`make film FILM=10` films more. Any run shorter than the 50 test tables writes
`partial.json`, never `results.json`.

## Results — 50 tables, 251 glasses, 203 without room at the start

| | |
|---|---|
| Tables | 14 done, 35 not finished, **1 wrong** |
| Glasses | 107 taken, 143 refused, **1 knocked over** |
| Pushes | 173, of which 63 were a second or later push of the same glass |
| Accuracy | glasses stopped 1.7 mm from where they were aimed (median), 57.6 mm at worst |

This page used to show 33 tables done and 195 glasses taken. The whole
difference is the gripper. The examiner used to push with an invented blade,
120 mm long and 28 mm thick. It now pushes with a real **Robotiq 2F-85**. That
hand is 139 mm across its fingers, so it must be turned on its side to fit
between glasses. On its side it cannot push lower than 75 mm. A push that high
tips glasses that a lower one would have slid. [The bench](../bench/README.md)
explains the hand.

The refusals now split three ways. The table counts the glasses left for each
reason. The split is the most useful thing on this page.

| why a glass was left | glasses |
|---|---|
| nowhere clear to push it to | 53 |
| tipped when tried | 49 |
| tips before it slides | 38 |
| stopped: a glass fell over | 3 |

The first group is the hand's width. There is free space on the table, but
the hand cannot reach into it. The next two are its height. So **this gripper
is refused about as often for being too tall as for being too wide**. The old
blade was only ever too wide.

**One glass went over, out of 251.** Compare that with the 33 per cent of
glasses that tip when pushed carelessly at this height. Almost all of the
danger is refused rather than met. The test push does less of that work than
it seems. The note below explains why.

## Two changes from the overview

**A test push instead of a guess.** The overview refuses any glass that would
tip if the friction were 0.5. That refused 35 of the first 60 glasses, far too
many. A 5 mm test push was meant to show the answer directly.

The first version pushed only 3 mm and wrongly refused 24 glasses. The first
0.5 to 2.5 mm of any push is lost before the glass starts to move, and up to
6 mm on a thin stem. So the push is 5 mm, and three looks are averaged before
and after.

**That test push no longer tells the two cases apart. It is left in on
purpose.** At 75 mm up instead of 50, a glass about to tip leans first. The
lean takes up the whole 5 mm. Across the four families, a glass that the full
push would slide moves under a millimetre during the test. That is inside the
error of the looks. No length from 5 to 20 mm separates the cases either, so
this is not a threshold to retune.

Its mistakes all point one way, and that saves it. It says "it tipped" about
some glasses that would have slid. So the arm refuses glasses it could have
moved. A refusal is a result and can be reported. It never calls a glass safe
and then topples it, which is the error that costs a glass.
`test_programmed.py` checks that direction and nothing else. So most of the
87 glasses refused for tipping were refused by the arithmetic, not by the
test push.

**Loosening a tight group.** Pushing only when one push fully frees a glass
left 107 glasses stuck. Allowing pushes that loosen the group cut that to
50.
