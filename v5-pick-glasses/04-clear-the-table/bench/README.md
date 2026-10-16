# Problem 4 — the shared test bench

Every solution in `../` runs on this bench. They are all given the same drawn
tables, the same camera carried on the arm, the same physics and the same
scorecard, so that when two solutions differ, the difference is the solution
and nothing else.

The bench is small, and that is because most of it is problem 3's bench, used
from here rather than rewritten. That borrowing is the decision this folder
turns on, so it comes before the list of modules.

## What is borrowed from problem 3, and why it is borrowed

Problem 4 is problem 3's task with the overhead camera and the push-by-push
hand-over taken away. Nothing underneath those two absences changes. The table is
the same table, the glasses are the same glasses, the jaw is the same closed
Robotiq 2F-85 held a quarter turn over, the physics and the friction are the
same, the arithmetic that decides whether a glass slides or tips is the same,
and every reading still carries problem 2's measured error. So problem 4
**imports** problem 3's bench. It does not copy it.

Copying would have been simpler to read on the first day and wrong on every day
after, for two reasons.

**A copy drifts.** The day either side changes a friction value, the jaw's
shape, or the error on a measured width, the two benches stop agreeing. Nobody
notices, because each bench still passes its own tests. The divergence shows up
much later, as results that cannot be explained.

**A copy destroys the comparison.** The whole question problem 4 asks is what
those two absences cost, and the only way to answer it is to subtract problem
4's numbers from problem 3's. That subtraction means something while both sets
of numbers come from one cell. Measured on two benches that have quietly grown
apart, it means nothing at all.

The borrowing is kept on one page. `partners.py` imports everything problem 4
takes from problem 3, and every other file here imports it **from
`partners`**, never from `bench` directly. A reader can then see the whole debt
to problem 3 in one file, and when problem 3 moves something, one file breaks
instead of six. Finding problem 3 on disk is not this folder's job either:
`pixi.toml` puts problem 3's `bench` folder on `PYTHONPATH`, and `partners.py`
adds only problem 3's solution 1, whose folder name begins with a digit and so
can never be imported as a package.

If you need something problem 3's bench does not offer, add it here in
`04-clear-the-table/bench/`, with a comment saying why it could not be
borrowed. Nothing under `03-push-glasses-apart/` is edited to make problem 4
work.

### What is deliberately not borrowed

Three things in problem 3 belong to problem 3's own protocol, and taking them
would have taken the problem with them.

- **The overhead picture.** It is written into the world XML as a fixed camera
  and cannot be moved, which is exactly the convenience problem 4 removes.
  `wrist.py` renders its own picture instead, from wherever the jaw is
  standing.
- **The push-by-push scorecard.** Problem 3's `Scorecard` counts pushes and
  marks them one at a time, and problem 4 has no pushes to count. Two of its
  functions are free of that protocol — `spread`, which reports the middle and
  the range of every number over repeated runs, and `save_tables`, which
  writes the per-table rows beside a scorecard — and those two are borrowed.
- **Racking a glass.** `take()` belongs to problem 3's clearing score. A
  problem 4 table ends with every glass still standing on it, and the question
  asked of each glass is only whether it now has room.

## The modules

`contract.py` holds the shapes that a solution and the bench pass to each
other: `Look`, `Done`, `Answer`, `TableResult` and the `Solution` protocol. It
holds no behaviour, so that every other file can agree on it without depending
on anything. No module defines its own version of these, and a field that is
missing from it is discussed before it is added.

`partners.py` is the borrowing described above, and the only file here that
reaches into problem 3.

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

`film.py` records a table being cleared, for looking at by eye. It changes
nothing: the table is scored in the world the bench builds and everything the
film draws is drawn in a second world of its own, which `test_film.py` checks
by running one table both ways and comparing the results. A frame shows the
table from the arm's side and, in the corner, the last picture the arm's own
camera gave the solution, which is everything the solution knew when it chose.
The recording itself is borrowed from problem 3's `film.py` rather than written
again. `../results/films.py` is what drives it, one solution at a time.

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

**This bench has measured nothing yet.** Problem 4 is being built; the examiner
has not been run on any solution, so there are no scores here, no counts of
toppled glasses and no arm times. When those arrive they will be in the
solution documents under
[`docs/04-clear-the-table/solutions/`](../../docs/04-clear-the-table/solutions/),
each with the spread over repeated runs, because a result quoted without a
spread is not a result.

What is already measured is the cell, and it is measured in problem 3. The
friction, the measurement error on each reading, the jaw's real dimensions, the
height it rides at and how often a careless push topples a glass are all stated
in [problem 3's bench README](../../03-push-glasses-apart/bench/README.md).
Those numbers hold here unchanged, which is the point of borrowing the cell,
and they are not restated in this file so that there is only one place to
correct them.
