# Problem 3 — the shared test bench

Every solution in `../` uses this bench. They all run on the same tables, get
the same measurements, push with the same jaw, face the same physics, and are
judged by the same scorecard.
[The examiner](../docs/the-examiner.md) explains why
it is built this way.

- `bench.py`: the numbered tables, and a MuJoCo world to push glasses around
  in. It stands in for Gazebo. Tables from 10000 up are for testing only.
- `top_view.py`: the table from directly above, for the solutions that read
  pictures rather than numbers.
- `scoring.py`: judges a run against what the physics really did. No solution
  reads it to decide anything.
- `film.py`: a bench that also records a video, for checking by eye what the
  hand did. The film is drawn in a second world of its own, so the scored
  physics is unchanged. There is still no arm: the hand moves on its own.
  `make comparison-films` uses it to film one table with each of the six
  solutions. The documents link to those films.

## What a film shows, and what it does not

Two things in the films are not what a first look suggests.

**The hand never opens during a push.** This problem pushes glasses with the
gripper held shut. A push is the whole hand driven sideways into a glass.
Nothing is gripped or lifted. If the fingers opened during a push, the film
would be wrong.

**A pick is drawn, not simulated.** `take()` removes a glass from the table in
one instant, which on film would look like the glass vanishing. So the film
draws a stand-in pick: the wrist rolls back level, the fingers open to the
measured width, the hand reaches in, the fingers close, and the glass is
carried off. A label on screen says so, and says that problem 1 does the real
pick. Nothing in it is stepped. `test_bench.py` checks that a filmed table ends
exactly where the same unfilmed table ends.

A drawn hand cannot collide with anything. So the way in is checked before it
is drawn, with the same geometry solution 1 uses. If no side is clear, the hand
is drawn stopping where it would touch, with a line on screen saying so.
[The examiner](../docs/the-examiner.md#what-push-does-and-what-it-reports-back)
explains why room round a glass is not the same as a way in.

The drawn pick keeps problem 1's two height bounds: no lower than 50 mm, where
the force sensor would meet the table, and no higher than halfway up the glass.
It is still not problem 1's grip rule.
[The examiner](../docs/the-examiner.md) counts how
many glasses that rule refuses, and [known-gaps.md](../../01-rack-one-glass/docs/known-gaps.md)
explains why that is a gap in problem 1.

One more thing is deliberate. The hand is drawn twice: its real pieces solid,
and around them, as a faint shell, the larger shape the bench collides with.
The bench treats each pair of fingers as one box covering both fingers and the
82 mm gap between them. That is the safe choice for a push, because a glass in
that gap would be swept along anyway. The shell is what solutions must plan
around. The pieces are what a real hand looks like.

## What an approach gets

The table below lists every call a solution may make.

| Call | What it does |
|---|---|
| `look()` | Each glass still on the table: where it stands, its height, its widest width, its foot width, and whether it is standing. This is what problem 2's camera work hands over. Every reading carries problem 2's measured error: 0.5 mm in position, 2.5 mm in width, 1.2 mm in height (one standard deviation). The error is fresh on every look and seeded by the table and the look number, so the first look is the same for every solution. |
| `push(Push)` | The closed jaw comes down at a start point to 75 mm above the table (`PUSH_HEIGHT`). It feels forward until it touches (0.1 N), pushes a set distance, backs off 20 mm and goes up. It reports what it felt: blocked on the way down, how far it went before touching, whether it jammed, and the peak force. |
| `take(id)` | Pick the glass up and rack it. Problem 1 does the real pick. The bench records whether the glass really had room. |
| `follow(Chunk)` | The other door for the same thing: a short run of jaw waypoints, carried out one `WAYPOINT_PERIOD` (50 ms) apart in the same physics. It reports the same `Felt` into the same record, so the scorecard cannot tell which door was used. For a policy whose answer is already a trajectory. |
| `top_view(bench)` | The table from directly above, 750 mm up, as a 384 x 384 RGB `uint8` array. See `top_view.py` for the frame and the colours. |

A `Record` also keeps the path the jaw really followed, sampled every
`WAYPOINT_PERIOD`. Replay it with `follow()` and the same push happens again.
That turns a parameterised push into a demonstration for a policy that emits
waypoints.

## The push budget

`PUSHES_PER_GLASS` (4) and `PUSHES_PER_TABLE` (16) live here, so push counts
mean the same thing for every solution. `01-one-fixed-nudge` predates them and
keeps its own 3 and 15, because its committed scorecard was measured at those
numbers.

**A glass refused for "push budget spent" was not necessarily cut short.** The
reason records where a run stopped, not why it went badly. The budget binds
only where pushes are wasted. Solutions 1 and 2 never spend it in fifty tables,
and `04-a-world-model` spends it for ten glasses of 251. It was tested on
`03-imitation-from-demonstrations`, where it is the commonest refusal. Raising
the budget eightfold moved its score by one or two glasses of 251, while its
pushes rose from about 440 to about 3,000. The budget was then left as it is,
because changing it would have meant tuning against these fifty held-out
tables.
[The solution's document](../docs/solutions/03-imitation-from-demonstrations.md)
holds the table.

## Repeats and the compute column

`Scorecard` is one evaluation run. A stochastic solution uses `Repeats`. It
holds several runs and reports the median, the standard deviation and the range
of every number.

Pass `seconds=` to `Scorecard.scene()`: the wall time the solution spent on
that table. The scorecard then reports `seconds_per_push`, with the bench's own
time taken off, so what is left is the thinking. Leave it out and no time is
reported. An unmeasured cost is absent, not zero.

## What is hidden

- **Friction.** Glass on the table is 0.35 (`TABLE_FRICTION`), the same on
  every table. No solution reads it.
- **The glasses' true positions, masses and shapes.** Only `scoring.py`, and a
  learned solution's training labels, use them.

## The jaw

A real **Robotiq 2F-85**, closed, pointing the way it pushes. Its shape is not
drawn by hand here. `arm/robotiq_2f85.py` turns the link offsets and collision
meshes that Robotiq publish into the boxes this bench loads. So the hand that
pushes here is the hand the cell in `src/` grips with.

The table below gives each part of the hand, measured back from the
fingertips, which reach a glass first.

| stretch | how far back it starts | how wide |
|---|---|---|
| the two fingertips, meeting in the middle | 0 mm, for 57 mm | 27 mm |
| the fingers behind them | 35 mm, for 59 mm | 27 mm |
| the body | 73 mm, for 93 mm | 75 mm |
| the force sensor and the wrist | 166 mm, for 100 mm | 89 mm |

**The hand is held rolled a quarter turn. That is the only choice this bench
makes about it**, and it decides whether the problem works at all.

Held the way the cell grips a glass, with the two fingers side by side, the
hand is **139 mm across**. The glasses here stand 150 mm apart centre to centre
at the closest. So a hand that wide has almost nowhere to go. On the held-out
tables, solution 1 made **three pushes in forty-nine tables**. It left 201 of
its 245 glasses standing with "nowhere clear to push it to". That is not a bug.
It is what a real 2F-85 does to this task. The thin blade this problem used to
assume, 120 mm long and 28 mm thick, had hidden it.

Rolled a quarter turn, the two fingers stack one above the other. The hand is
then 27 mm across, narrower than the old blade, and the task is possible again.

Rolling costs height. On its side the hand reaches 69 mm below its own middle.
So it cannot ride at 50 mm as before, because its fingers would hit the table.
It rides at **75 mm**, as low as it can go with five millimetres to spare. That
height comes from the hand's own size. It was not chosen by trying several
heights on the held-out tables, because that would make every later result a
measure of the tuning.

Pushing 25 mm higher up a glass matters. It is now the hardest thing about
this problem. Pushed carelessly at this height, **about a third of glasses tip
over instead of sliding**: six of twelve tapered glasses and eight of twelve
short-stemmed ones, while a tumbler never tips. Avoiding that is most of what
separates the six solutions, because a toppled glass is a *wrong* outcome.

The jaw's top edge is 107 mm up. A glass that is wider higher up meets the jaw
there first, so that is the height it is really pushed at.
[Pushing without toppling](../docs/pushing-without-toppling.md#the-height-that-counts-is-the-top-edge-of-the-jaw)
explains what that does to the topple limit.

## Tables

Four to six glasses of one kind, with the kind and count cycling as in problem
2. About six in ten are stood deliberately between touching and having room.
None touch, and every table has at least one glass without room. A glass has
room when no other glass's edge is within 76 mm of its middle (`has_room`).
That is how far the open hand reaches either side of its own middle.

## Outcomes

- **done:** every glass racked, each while it really had room.
- **incomplete:** glasses left on the table, each with a reason, and nothing
  wrong.
- **wrong:** a glass toppled, left the glass zone, was picked without room, or
  was left with no reason.
