# Problem 4 — clear the table

Problem 4 asks for problem 3's task again: some glasses on the table stand too
close together for the gripper to get round one without fouling its neighbour,
and the arm has to push them apart across the table rather than lift them.
What makes it a new problem is what has been taken away. Two helps that
problem 3 gave a solution are gone, and those two absences are the whole of
problem 4.

**The camera above the table is gone.** The arm carries its own camera now, so
seeing costs motion and time. A solution that wants to know what is in the far
corner of the table has to take the arm there first. An overhead camera is a
convenience of the simulator, and the cell this project is built for does not
have one.

**The push-by-push hand-over is gone.** In problem 3 the bench asked for one
push, carried it out, marked it and asked again. Here a solution runs on its
own — it looks, it acts, it looks again — and it **says when the table is
finished**. Nothing else decides that the work is done, because a real cell has
nobody standing by to count the pushes.

The full statement is GitHub issue #23 of `RobinNagpal/robot-arm-projects`, and
it is written up in [`docs/04-clear-the-table/`](../docs/04-clear-the-table/README.md):
[`problem.md`](../docs/04-clear-the-table/problem.md) for what goes in and what
must come out, and [`the-examiner.md`](../docs/04-clear-the-table/the-examiner.md)
for how a run is marked. Read those two before any solution document.

## How a run is marked

The tables are drawn, not chosen. Every table holds three to five glasses, with
one touching group -- a pair on some tables and three glasses on others -- and
one or two glasses that already have room. The composition changes with the
table number on purpose: a table that always holds the same arrangement is a
constant that a trained solution can memorise instead of learning to separate
glasses. An earlier draw asked for four to seven glasses with a touching pair
*and* a touching group of three, and it turned out to be unsolvable rather than
hard; [`bench/tables.py`](bench/tables.py) says what was measured and why it
was changed.

**The budget is arm time, not laptop time.** It is counted in simulated seconds
of arm motion, summed from the waypoints the arm carried out and the speeds it
carried them out at. Looking costs arm time as well, because the camera has to
be moved to see. Thinking time is recorded next to it, the way problem 3
records it, but it is not what the budget is spent on.

**The cell keeps its tipping check.** A glass that the physics says would topple
rather than slide is left alone, because a real cell keeps its safety
interlocks. That is the only thing the cell still does on a solution's behalf;
it no longer counts pushes and it no longer filters trajectories.

**A toppled glass fails that table, and the run carries on.** Broken glass
leaves shards, so a topple is a wrong outcome and not merely an unfinished one,
but it never fails the whole run and there is no free breakage.

A run reports glasses broken, tables separated with nothing broken, tables
failed by a topple, tables left unfinished when the clock stopped, glasses made
pickable out of all glasses, the average arm time for a table that succeeded,
and how often the solution declared itself done. Whether a glass is pickable is
worked out from the gripper's own numbers and the glass's measured width. No
glass's size is written down anywhere, which is this project's first rule.

## What is in this folder

```
pixi.toml ruff.toml Makefile README.md   environment and entry points
bench/                                   the shared bench, see bench/README.md
  contract.py       the shapes a solution and the bench pass to each other
  partners.py       everything borrowed from problem 3, in one place
  tables.py         the draw
  clock.py          simulated arm time
  wrist.py          the camera carried by the arm
  open_run.py       the loop: look, act, declare done, stop on the budget
  scoring.py        the end-state scorecard
  judging.py        the held-out queue, and the one way a result is recorded
  stopping.py       how a trained policy says it has finished
  keeping_clear.py  the clearance check a solution runs over its own answer
  film.py           recording a table being cleared, for looking at by eye
  test_*.py         one test file per module above
demonstrations/                          the teacher's answers, for the two fitted solutions
01-one-fixed-nudge/                      the geometry reference, ported
02-geometry-ranked/                      the same loop, with fitted trees ordering the pushes
03-imitation-from-demonstrations/        a gate that decides and a chunked policy that draws
04-a-world-model/                        a fitted model of what a push does, and a search
05-smolvla-as-it-downloads/              a borrowed foundation model, nothing fitted
06-smolvla-fine-tuned/                   the same weights, corrected on this cell
results/                                 the six side by side, and the films
```

The documents live apart from the code, in
[`docs/04-clear-the-table/`](../docs/04-clear-the-table/README.md), and each
solution has a document of its own under `solutions/` there.

## How to run it

`make help` lists the targets. The three that matter are `make install`, which
resolves this folder's environment, `make test`, which runs every folder's
tests one folder at a time, and `make lint`, which runs Ruff over everything.

This folder's environment is new and may not be resolved on your machine yet.
Until it is, `make test-in-problem-3` runs the same tests inside problem 3's
environment, which already has everything problem 4 needs. Both commands run
the same test files; only the environment around them differs.

Keep test runs short. The tests are meant to take a handful of tables and a few
seconds of simulated arm time, because this project shares one machine with the
model fitting that problem 3 does.

## What has been measured

**All six solutions, on the held-out queue of fifty tables, walked three times
each.** [`results/README.md`](results/README.md) is the comparison: every
column, what perfect play achieves on exactly the tables each solution reached,
and which columns mislead when they are read on their own. Each solution's own
folder holds its `results.json` and the per-table rows behind it, and each has a
document of its own under
[`../docs/04-clear-the-table/solutions/`](../docs/04-clear-the-table/solutions/).

**Every solution was also measured twice over, before and after a round of
changes made to the fitted ones.**
[`../docs/04-clear-the-table/what-changed.md`](../docs/04-clear-the-table/what-changed.md)
is the record of what was changed, what each change bought, and which proposed
changes were measured and then dropped. Read it with the comparison page: the
page says where each solution stands, and the record says how it got there.

What carries over from problem 3 is everything measured about the cell itself,
because problem 4 pushes the same glasses through the same physics with the same
jaw. Those numbers are in
[problem 3's bench README](../03-push-glasses-apart/bench/README.md), and
`bench/README.md` here explains why problem 4 borrows that cell rather than
copying it.
