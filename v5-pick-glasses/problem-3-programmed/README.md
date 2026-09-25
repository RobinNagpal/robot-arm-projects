# Problem 3 — the programmed way

Some glasses stand too close together for the gripper to get round them. The
arm pushes them apart across the table, then picks them up. Everything here is
geometry and simple physics: no training, no model.

It follows solutions 1 and 3 of
[the solution overview](../docs/problem-3/solution-overview.md), with two
changes explained at the end.

## Words used below

- **Room.** A glass has room when every other glass's edge is at least 70 mm
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

Limits: 3 pushes per glass, 15 per table.

## Where the code is

| File | What it does |
|---|---|
| `run.py` | The loop above, and the scoring run |
| `plan.py` | The tipping check, the test push, and the search for a safe push |
| `../problem-3-sim/` | The tables, the physics (MuJoCo) and the scoring, shared with `problem-3-learned` |

## Running it

```
make run        # the 50 test tables; writes results.json
make film       # videos of the first 3 test tables, in videos/
make test
```

`make film FILM=10` films more. Any run shorter than the 50 test tables writes
`partial.json`, never `results.json`.

## Results — 50 tables, 251 glasses, 190 without room at the start

| | |
|---|---|
| Tables | 35 done, 15 not finished, **0 wrong** |
| Glasses | 199 taken, 52 refused, **0 knocked over** |
| Pushes | 212, of which 92 were 5 mm test pushes |
| Accuracy | glasses stopped 1.0 mm from where they were aimed (median), 3.9 mm at worst |

All 52 refused glasses were "nowhere clear to push it to". There was free
space on the table, but the jaw could not get behind the glass. The body
behind the fingers is 90 mm wide, and in a tight group it would hit a
neighbour.

**On 100 more tables (9500 on) it knocked one glass over.** A tapered glass
passed its 5 mm test push, then tipped about 40 mm into the real push. The
test push checks how the glass starts to move, not the whole push. This was
left as it is and reported, not tuned away.

## Two changes from the overview

**A test push instead of a guess.** The overview refuses any glass that would
tip if the friction were 0.5. That refused 35 of the first 60 glasses, far too
many. A 5 mm test push shows the answer directly.

The first version pushed only 3 mm and wrongly refused 24 glasses. The reason
is that the first 0.5 to 2.5 mm of any push is lost before the glass starts to
move (up to 6 mm on a thin stem). Hence 5 mm, and three looks averaged before
and after.

**Loosening a tight group.** Pushing only when one push fully frees a glass
left 107 glasses stuck. Allowing pushes that loosen the group brought that
down to 50.
