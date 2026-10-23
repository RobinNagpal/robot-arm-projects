# Problem 4 — the shared examiner

This examiner is the first cell of problem 4, the one in which the jaw moves on
its own with no arm behind it. Every solution in the numbered folders of `../`
runs on it. They are all given the same drawn tables, the same camera carried
on the wrist, the same physics and the same scorecard, so that when two
solutions differ, the difference is the solution and nothing else.

The whole-arm cell in [`../full-arm/`](../full-arm/README.md) is built on this
examiner too. It does not use the loop here, because there a solution is handed
the arm and runs the table itself, but it draws its tables with `tables.py`,
builds its camera on the one in `wrist.py` with only the mounting changed, takes
its physics settings through `partners.py`, and marks every table with `scoring.py`. So a number
from either cell is read on the same scale. The solutions that run here also
run on the arm, through `../full-arm/jaw_solutions.py`, which shows each of
them the same kind of look this examiner does.

The examiner is small, and that is because most of it is problem 3's examiner, kept
here as a copy rather than rewritten. That copy is the decision this folder
turns on, so it comes before the list of modules.

## What is taken from problem 3, and why it is a copy

Problem 4 is problem 3's task with the overhead camera and the push-by-push
hand-over taken away. Nothing underneath those two absences changes. The table is
the same table, the glasses are the same glasses, the jaw is the same closed
Robotiq 2F-85 held a quarter turn over, the physics and the friction are the
same, the arithmetic that decides whether a glass slides or tips is the same,
and every reading still carries problem 2's measured error. So problem 4
runs on the part of problem 3's examiner that both problems need.

Problem 3 keeps that part in three common files of its own: `common_bench.py`
for the physics, `common_scoring.py` for reporting a spread, and
`common_film.py` for the recording. Its own `bench.py`, `scoring.py` and
`film.py` extend them with what belongs to problem 3 alone. Problem 4 keeps
copies of only the three common files, and of the few problem 3 solution files
it builds on, in [`../from-problem-3/`](../from-problem-3/README.md). They are
copies so that the two problems share no code, and each folder can be read, run
and changed on its own.

A copy has one cost, and it is worth knowing. **A copy can drift.** If problem
3 later changes a friction value, the jaw's shape, or the error on a measured
width, the copy here does not change with it. Nothing warns about this, because
each examiner still passes its own tests. The question problem 4 asks is what the
two absences cost, and it is answered by setting problem 4's numbers beside
problem 3's. That comparison holds only while the copy matches problem 3's
files, so the copy is kept exactly as problem 3 had it.

What is taken is kept on one page. `partners.py` imports everything problem 4
takes from the copy, and every other file here imports it **from
`partners`**, never from the copies directly. A reader can then see the whole
debt to problem 3 in one file. `pixi.toml` puts the copy's folder, `from-problem-3/bench/`, on
`PYTHONPATH`, and `partners.py` adds only the copy of problem 3's solution 1,
whose folder name begins with a digit and so can never be imported as a
package.

If you need something problem 3's examiner does not offer, add it here in
`examiner/`, with a comment saying why the copy does not have it. Nothing under
`from-problem-3/` is edited to make problem 4 work.

### What is deliberately not copied

Three things in problem 3 belong to problem 3's own protocol, and taking them
would have taken the problem with them. They are in problem 3's own halves of
its files, so they are not in the copy at all.

- **The overhead picture.** Problem 3 writes it into its world as a fixed camera
  that cannot be moved, which is exactly the convenience problem 4 removes. The
  common world has no fixed camera, so problem 4's world has none either.
  `wrist.py` renders its own picture instead, from wherever the jaw is
  standing.
- **The push-by-push scorecard.** Problem 3's `Scorecard` counts pushes and
  marks them one at a time, and problem 4 has no pushes to count. Two of its
  functions are free of that protocol — `spread`, which reports the middle and
  the range of every number over repeated runs, and `save_tables`, which
  writes the per-table rows beside a scorecard — and problem 3 keeps those two
  in `common_scoring.py`, which is copied.
- **Pushing by feel, and racking a glass.** Problem 3's `push()` comes down,
  feels forward until it touches, and pushes, and its `take()` racks a glass.
  Both belong to problem 3's protocol. A problem 4 solution moves the jaw only
  by a list of waypoints, which the common simulator's `follow()` carries out, and a
  problem 4 table ends with every glass still standing on it. The question
  asked of each glass is only whether it now has room.

## The modules

`contract.py` holds the shapes that a solution and the examiner pass to each
other: `Look`, `Done`, `Answer`, `TableResult` and the `Solution` protocol. It
holds no behaviour, so that every other file can agree on it without depending
on anything. No module defines its own version of these, and a field that is
missing from it is discussed before it is added.

`partners.py` is the copy's single entrance, described above, and the only
file here that reaches into `from-problem-3/`.

`simulator.py` holds `Simulator`, one of problem 4's tables in the physics
engine. It extends the common simulator, which is problem 3's `CommonBench`, and
the one thing it adds is problem 4's own draw: given only a table number, it
stands that table's glasses from `tables.py`, where problem 3's own class would
stand problem 3's. The whole-arm cell's `ArmSimulator` extends this class.

The copies of problem 3's solution files import what they need from a module
they call `bench`, which is problem 3's name for its own module. So
`partners.py` answers to that name as well, and the copies stay exactly as
problem 3 has them.

`tables.py` is the draw. `table(seed)` returns the glasses to stand on one
table and `facts(seed)` says what was drawn. Every table holds three to five
glasses: one touching group, which is a pair on about half the tables and three
glasses on the rest, and one or two glasses that already have room. The number
of crowded glasses stays inside a narrow band so that tables differ less from
one another. An earlier draw asked for four to seven glasses with a touching
pair and a group of three on every table, and it was replaced because perfect
play separated none of twenty such tables, so nothing could be ranked on it.
The arrangement still varies with the seed, because a constant arrangement is
something a trained solution can memorise instead of learning the task. Every
crowded glass is one the physics can slide rather than tip, checked with
solution 1's own arithmetic and redrawn until that holds, so a table is always
solvable in principle. Glasses start a small gap apart, never overlapping, and
always inside the zone.

`clock.py` is the arm's own time. It says what a path costs in simulated
seconds by mirroring the rule `follow()` already uses, rather than inventing a
second rule that would slowly disagree with the first, and it keeps a small
accumulator of what has been spent and what is left. A look is costed through
the same function, because moving to see is moving.

`wrist.py` is the camera the arm carries. One class renders the table from the
jaw's pose, and one function says which glasses fall inside that picture. The
picture is the same size as problem 3's overhead one, 384 by 384, so that a
learned solution can later reuse the shapes it was built around. The comment in
that file says why the camera is mounted on the wrist looking forward and down.

`open_run.py` is the loop. `clear_table(solution, seed, budget, ...)` looks,
asks the solution for an answer, carries it out and looks again, until the
solution says it is done, the budget runs out, or a glass goes over. The cell
keeps its tipping interlock here: it will not drive the jaw into a glass the
physics says would tip rather than slide, and it records how often that
happened. Nothing else is filtered on the solution's behalf.

`scoring.py` is the end-state scorecard. `pickable(...)` answers whether the
gripper could get round one glass, from the gripper's own numbers and that
glass's measured width — never from a size written down. The card adds up
`TableResult`s and reports glasses broken, tables separated with nothing
broken, tables failed by a topple, tables left unfinished, glasses made
pickable out of all glasses, the average arm time for a table that succeeded,
and how often the solution declared itself done.

`keeping_clear.py` is the one module here that **no part of the examiner
calls.** It is arithmetic offered to the solutions, which each run it over their
own answer before handing it over, and it lives in this folder for the same
reason `clock.py` does: every solution can reach the examiner's modules, and one
copy of a piece of arithmetic cannot drift away from another. What it says is
that an answer is either a move at the height the jaw travels at, which nothing
on the table reaches, or a push at one named glass carried out at the height a
push works at — and that anything else, in particular a path travelling at the
height of the glasses' rims, is raised to travel height before the arm moves.
The cell's own interlock is narrower on purpose and is unchanged by it: that
refuses a path into a glass the tipping rule flatly refuses, and nothing more.
The first walks of the learned solutions broke most of their glasses on paths
the interlock had no question to ask about, which is why the solutions now ask
one of their own.

`film.py` records a table being cleared, for looking at by eye. It changes
nothing: the table is scored in the world the examiner builds and everything the
film draws is drawn in a second world of its own, which `test_film.py` checks
by running one table both ways and comparing the results. A frame shows the
table from the arm's side and, in the corner, the last picture the arm's own
camera gave the solution, which is everything the solution knew when it chose.
The recording itself is problem 3's `common_film.py`, which this file
extends, rather than being written again. `../results/films.py` is what drives it, one solution at a time.

Each module has one test file beside it, `test_<module>.py`. Tests here run
against families of glasses rather than single examples, because a rule that
works on one wine glass and fails on a differently proportioned one is the
failure this project exists to prevent.

## Which tables are for testing

`TEST_SEEDS` is borrowed from problem 3 along with the rest, so the line
between the tables a solution may be developed on and the held-out tables it is
marked on falls in the same place in both problems. A table numbered at or
above it is for marking only.

## Numbers

The results of the solutions that run on this examiner are on the comparison page,
[`../results/README.md`](../results/README.md), and in each solution folder's
own `README.md`. Each is given with its spread over repeated walks, because a
result quoted without a spread is not a result. The results of the whole-arm
cell are in [`../docs/README.md`](../docs/README.md#results).

What this examiner does not measure is the cell itself, because that was measured
in problem 3. The friction, the measurement error on each reading, the jaw's
real dimensions, the height it rides at and how often a careless push topples a
glass are all stated in
[problem 3's examiner README](../../03-push-glasses-apart/bench/README.md). Those
numbers hold here unchanged, because the copy in `from-problem-3/` is kept
exactly as problem 3 has it. They are not restated in this file, so that there
is only one place to correct them.
