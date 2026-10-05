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
  jaw did. The physics is the same; it only looks after each step. A take
  is shown as the jaw lifting the glass and carrying it off towards the
  rack, drawn on a copy of the world, so a glass never just vanishes and the
  results are the same filmed or not. There is still no arm: the jaw moves on
  its own. Both approaches use it for `make film`.

## What an approach gets

| Call | What it does |
|---|---|
| `look()` | Each glass still on the table: where it stands, its height, its widest width, its foot width, and whether it is standing. This is what problem 2's camera work hands over. Every reading carries problem 2's measured error: 0.5 mm in position, 2.5 mm in width, 1.2 mm in height (one standard deviation). The error is fresh on every look and seeded by the table and the look number, so the first look is the same for both approaches. |
| `push(Push)` | The closed jaw comes down at a start point to 50 mm above the table (`LOWEST_GRIP`). It feels forward until it touches (0.1 N), pushes a set distance, backs off 20 mm and goes up. It reports what it felt: blocked on the way down, how far it went before touching, whether it jammed, and the peak force. |
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

The closed gripper from `arm/gripper.urdf.xacro`, held level and pointing the
way it pushes:

- the fingers: 120 mm long, 28 mm thick, 30 mm tall;
- the body and the wrist behind them: 150 mm long, 90 × 90 mm.

The jaw's top edge is 65 mm up. A glass that is wider higher up meets the jaw
there first, so that is the height it is really pushed at.

## Tables

Four to six glasses of one kind, with the kind and count cycling as in problem
2. About six in ten are stood deliberately between touching and having room.
None touch, and every table has at least one glass without room. A glass has
room when no other glass's edge is within 70 mm of its middle (`has_room`).

## Outcomes

- **done:** every glass racked, each while it really had room.
- **incomplete:** glasses left on the table, each with a reason, and nothing
  wrong.
- **wrong:** a glass toppled, left the glass zone, was picked without room, or
  was left with no reason.
