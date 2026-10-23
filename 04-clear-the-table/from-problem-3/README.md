# Problem 3's files, copied

Problem 4 is built on problem 3's examiner, which problem 3 keeps in its `bench/` folder, on
problem 3's geometry planner, and on problem 3's ranked solution. This folder holds problem 4's own copy of exactly those files,
so that problem 4 shares no code with problem 3 and its folder can be read, run and changed on
its own.

Problem 3 splits each of its shared examiner files in two: a common half, which holds what
both problems need, and problem 3's own half, which extends it with what belongs to problem 3
alone, such as its overhead camera and the push that feels for a glass. Problem 4 copies only
the common halves it uses. Everything here is reached through
[`../examiner/simulation/taken_from_problem_3.py`](../examiner/simulation/taken_from_problem_3.py), except problem 3's
ranked solution, which solution 2 loads itself.

The copies are kept exactly as problem 3 has them, at the same paths inside their folders.
That matters because problem 4's results are compared with problem 3's, and the comparison
holds only while the two push the same glasses with the same physics. So a change belongs in
problem 4's own folders, never in these files. If problem 3 changes one of them, copy it here
again.

| Copied from `03-push-glasses-apart/` | Used by |
|---|---|
| `bench/common_bench.py` | the physics of the table and the glasses, which problem 4's `examiner/simulation/table_simulator.py` extends |
| `bench/common_scoring.py` | the spread over repeated runs, for problem 4's `examiner/examining/table_scoring.py` |
| `bench/top_view.py` | the size and lens of problem 3's picture, which the arm's camera keeps |
| `01-one-fixed-nudge/plan.py` | problem 3's geometry planner, which solutions 1 and 2 and the table draw use |
| `02-geometry-ranked/candidates.py`, `features.py`, `ranker.py` | problem 3's list of safe pushes and its fitted trees, which solution 2 orders its pushes with |

Solution 2 also reads problem 3's fitted trees, `02-geometry-ranked/model/`. They are not kept
in git. Problem 3 makes them with `make train` in its `02-geometry-ranked` folder, and they are
copied here from there.
