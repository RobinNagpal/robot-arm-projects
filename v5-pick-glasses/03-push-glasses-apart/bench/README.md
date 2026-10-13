# Problem 3 — the shared test bench

Used by every solution in `../`. All of them run on the same tables, get the
same measurements, push with the same jaw, face the same physics, and are
judged by the same scorecard.

- `bench.py` — the numbered tables and a MuJoCo world to push glasses around
  in. It stands in for Gazebo. Tables from 10000 up are for testing only.
- `top_view.py` — the table from directly above, for the solutions that read
  pictures rather than numbers.
- `scoring.py` — judges a run against what the physics really did. No
  approach reads it to decide anything.
- `film.py` — a bench that also records a video, for checking by eye what the
  hand did. The physics is the same, because the film is drawn in a second
  world of its own and the scored one is never added to. There is still no
  arm: the hand moves on its own. `make comparison-films` uses it to film one table
  with each of the six solutions, which is what the documents link to.

## What a film shows, and what it does not

The films are worth one paragraph of warning, because two things in them are
not what a first viewing suggests.

**The hand never opens during a push.** This problem shoves glasses apart with
the gripper held shut, which is what the parallel locking kit on a Robotiq
2F-85 is for, so a push is the whole hand driven sideways into a glass.
Nothing is gripped and nothing is lifted. If the fingers opened on film during
a push, the film would be wrong.

**A pick is drawn rather than simulated.** `take()` racks a glass by moving it
off the table in one instant, which on film would look like the glass
vanishing, so the film draws what a real pick-up is instead: the wrist turns
the hand upright, the fingers open to the width the glass was measured to be,
the hand comes down around it, the fingers close and the glass is carried off.
The label on screen says so while it happens. Nothing there is stepped, and
`test_bench.py` checks that a filmed table ends exactly where the same
unfilmed table ends.

Drawing that pick has to decide where the pads go, and the gripper's own
measurements decide it. The fingers reach about 33 mm past the pads before the
palm is in the way, so the glass is held within 33 mm of its own rim, which on
a tapered glass is its widest part; and the pads open 85 mm. Some glasses are
wider than that at the only height the palm allows, so no grip closes on them
and the film says so on screen. `take()` racks them all the same, because it
only asks whether a glass had room. [the-examiner.md](../../docs/03-push-glasses-apart/the-examiner.md)
counts them.

One more thing is visible and is deliberate. The hand is drawn twice: its real
pieces solid, and around them, as a faint shell, the larger shape the bench
collides with. The bench treats each pair of fingers as one box covering both
fingers and the 82 mm gap between them, which is the safe assumption for a
push, because a glass standing in that gap would be swept along just the same.
Seeing both at once is the point: the shell is what the solutions must plan
around, and the pieces are what a real hand looks like.

## What an approach gets

| Call | What it does |
|---|---|
| `look()` | Each glass still on the table: where it stands, its height, its widest width, its foot width, and whether it is standing. This is what problem 2's camera work hands over. Every reading carries problem 2's measured error: 0.5 mm in position, 2.5 mm in width, 1.2 mm in height (one standard deviation). The error is fresh on every look and seeded by the table and the look number, so the first look is the same for both approaches. |
| `push(Push)` | The closed jaw comes down at a start point to 75 mm above the table (`PUSH_HEIGHT`). It feels forward until it touches (0.1 N), pushes a set distance, backs off 20 mm and goes up. It reports what it felt: blocked on the way down, how far it went before touching, whether it jammed, and the peak force. |
| `take(id)` | Pick the glass up and rack it. Problem 1 does the real pick. The bench records whether the glass really had room. |
| `follow(Chunk)` | The other door for the same thing: a short run of jaw waypoints, carried out one `WAYPOINT_PERIOD` (50 ms) apart in the same physics. It reports the same `Felt` into the same record, so the scorecard cannot tell which door was used. For a policy whose answer is already a trajectory. |
| `top_view(bench)` | The table from directly above, 750 mm up, as a 384 x 384 RGB `uint8` array. See `top_view.py` for the frame and the colours. |

A `Record` also keeps the path the jaw really followed, sampled every
`WAYPOINT_PERIOD`. That is what turns a parameterised push into a
demonstration for a policy that emits waypoints: replay it with `follow()` and
the same thing happens.

## The push budget

`PUSHES_PER_GLASS` (4) and `PUSHES_PER_TABLE` (16) live here, so the push
counts mean the same thing across the six. `01-one-fixed-nudge` predates them
and keeps its own 3 and 15, because its committed scorecard was measured at
those numbers.

## Repeats and the compute column

`Scorecard` is one evaluation run. A stochastic solution uses `Repeats`, which
holds several and reports the median, the standard deviation and the range of
every number across them. A result quoted without a spread is not a result.

Pass `seconds=` to `Scorecard.scene()` — the wall time the solution spent on
that table — and the scorecard reports `seconds_per_push`, with the bench's own
time taken off, so what is left is the thinking. Leave it out and no time is
reported: an unmeasured cost is absent, not zero.

## What is hidden

- **Friction.** Glass on the table is 0.35 (`TABLE_FRICTION`), the same on
  every table. Neither approach reads it.
- **The glasses' true positions, masses and shapes.** Only `scoring.py`, and a
  learned approach's training labels, use them.

## The jaw

A real **Robotiq 2F-85**, closed, pointing the way it pushes. Its shape is not
drawn here: `arm/robotiq_2f85.py` turns the link offsets and collision meshes
that Robotiq publish into the boxes this bench loads, so the hand pushing
glasses here is the hand the cell in `src/` grips with.

Measured back from the fingertips, which are what reaches a glass first:

| stretch | how far back it starts | how wide |
|---|---|---|
| the two fingertips, meeting in the middle | 0 mm, for 57 mm | 27 mm |
| the fingers behind them | 35 mm, for 59 mm | 27 mm |
| the body | 73 mm, for 93 mm | 75 mm |
| the force sensor and the wrist | 166 mm, for 100 mm | 89 mm |

**The hand is held rolled a quarter turn, and that is the only decision this
bench makes about it.** It is worth understanding, because it is the difference
between this problem working and not working.

Held the way the cell grips a glass — the two fingers side by side, so the
opening direction lies flat — the hand is **139 mm across**. The glasses on
these tables stand 150 mm apart centre to centre at the closest, so a hand that
wide has almost nowhere to go. Measured over the held-out tables, solution 1
made **three pushes in forty-nine tables** and left 201 of its 245 glasses
standing with "nowhere clear to push it to". That is not a bug. It is what a
real 2F-85 does to this task, and the thin blade this problem used to assume —
120 mm long and 28 mm thick — had been hiding it.

Rolled a quarter turn, the two fingers stack one above the other and the hand
is 27 mm across, narrower than the blade it replaces, and the task is possible
again.

Rolling costs height, and that is the trade. On its side the hand reaches 69 mm
below its own middle, so it cannot ride at 50 mm as it used to: its fingers
would strike the table. It rides at **75 mm**, which is as low as it goes with
five millimetres to spare. That height is worked out from the hand's own size
and not chosen by trying several and keeping the best, because the fifty tables
here are the held-out set and tuning a number against them would make every
result afterwards a measurement of that tuning.

Pushing 25 mm higher up a glass matters, and it is now the hardest thing about
this problem. Pushed carelessly at this height, **about a third of glasses tip
over instead of sliding** — six of twelve tapered glasses and eight of twelve
short-stemmed ones, where a tumbler never tips. Avoiding that is most of what
separates the six solutions, because a toppled glass is a *wrong* outcome and
not merely an unfinished one.

The jaw's top edge is 107 mm up. A glass that is wider higher up meets the jaw
there first, so that is the height it is really pushed at.

## Tables

Four to six glasses of one kind, with the kind and count cycling as in problem
2. About six in ten are stood deliberately between touching and having room.
None touch, and every table has at least one glass without room. A glass has
room when no other glass's edge is within 76 mm of its middle (`has_room`),
which is how far the open hand reaches either side of its own middle.

## Outcomes

- **done:** every glass racked, each while it really had room.
- **incomplete:** glasses left on the table, each with a reason, and nothing
  wrong.
- **wrong:** a glass toppled, left the glass zone, was picked without room, or
  was left with no reason.
