# Problem 3 — the programmed way

Some glasses stand too close together for the gripper to get round them. The
arm pushes them apart across the table, then picks them up. Everything here is
geometry and simple physics: no training, no model.

It holds the candidate geometry that [one fixed
nudge](../../docs/03-push-glasses-apart/solutions/01-one-fixed-nudge.md) and
[geometry generates, a model
ranks](../../docs/03-push-glasses-apart/solutions/02-geometry-ranked.md) both use,
with two changes explained at the end.

## Words used below

- **Room.** A glass has room when every other glass's edge is at least 76 mm
  from its middle. That is the space the open gripper needs.
- **Take.** Pick a glass up and put it in the rack. Problem 1 does the real
  pick; here the glass is just lifted off the table.
- **Jaw.** The closed gripper, held level. It pushes with its fingertips. Its
  top edge is 65 mm above the table.

## The loop

The arm repeats these steps until the table is empty or nothing more can be
done.

**1. Look.** Get each glass's position, height, widest width and foot width
from the camera. If any glass has fallen over, stop.

**2. Take every glass that has room.** Each glass taken leaves more space for
the others, so sometimes no pushing is needed at all. Then look again.

**3. Check each glass can be pushed without tipping over.** A glass slides if
it is pushed low enough, and tips if pushed too high. The limit is

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

Limits: the push budget belongs to the bench, and every solution reads it
from there, so that the six are allowed the same number of tries.

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

These are much poorer than the figures this page used to carry — 33 tables done
and 195 glasses taken — and the whole of the difference is the gripper. The
examiner used to push with a blade 120 mm long and 28 mm thick, invented for
the purpose. It now pushes with a real **Robotiq 2F-85**, and that hand is
139 mm across its fingers, so it has to be turned on its side to fit between
glasses that stand 150 mm apart. Turned on its side it cannot push lower than
75 mm, and a push that high up tips glasses that a low one would have slid.
[The bench](../bench/README.md) explains the hand and why it is held that way.

The refusals now split three ways, and the split is the most useful thing on
this page:

| why a glass was left | glasses |
|---|---|
| nowhere clear to push it to | 53 |
| tipped when tried | 49 |
| tips before it slides | 38 |
| stopped: a glass fell over | 3 |

The first group is the hand's width: there is free space on the table, but
nothing the hand can reach into. The next two are its height. Together they
say that **this gripper is turned down about as often for being too tall as
for being too wide**, where the old blade was only ever too wide.

**One glass went over, out of 251.** That is worth holding against the 33 per
cent of glasses that tip when pushed carelessly at this height: almost all of
the danger is being refused rather than met. The test push is doing less of
that work than it looks, though — see the note on it below.

## Two changes from the overview

**A test push instead of a guess.** The overview refuses any glass that would
tip if the friction were 0.5. That refused 35 of the first 60 glasses, far too
many. A 5 mm test push was meant to show the answer directly.

The first version pushed only 3 mm and wrongly refused 24 glasses. The reason
is that the first 0.5 to 2.5 mm of any push is lost before the glass starts to
move (up to 6 mm on a thin stem). Hence 5 mm, and three looks averaged before
and after.

**That test push no longer tells the two cases apart, and it is left in on
purpose.** Pushing 75 mm up instead of 50, a glass that is about to tip leans
first, and the lean takes up the whole 5 mm: measured across the four
families, a glass the full push slides moves under a millimetre during the
test, which is inside the error of the looks themselves. No length between 5
and 20 mm separates them either, so this is not a threshold to retune.

What saves it is that its mistakes all point one way. It now says "it tipped"
about glasses that would in fact have slid, so the arm refuses glasses it could
have moved — a refusal, which is a result and can be reported. It never says a
glass is safe and then topples it, which is the error that costs a glass, and
`test_programmed.py` asserts that direction and nothing else. The honest
summary is that most of the 87 glasses turned down for tipping were turned down
by the arithmetic rather than by the experiment.

**Loosening a tight group.** Pushing only when one push fully frees a glass
left 107 glasses stuck. Allowing pushes that loosen the group brought that
down to 50.
