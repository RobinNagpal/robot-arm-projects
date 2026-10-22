# Problem 3's files, copied

Problem 4 is built on problem 3's bench and on a few of problem 3's solution
files. This folder holds problem 4's own copy of exactly those files, so that
problem 4 shares no code with problem 3 and its folder can be read, run and
changed on its own.

The copies are kept exactly as problem 3 has them, at the same paths inside
their folders. That matters because problem 4's results are compared with
problem 3's, and the comparison holds only while the two cells agree. So a
change belongs in problem 4's own folders, never in these files. If problem 3
changes one of them, copy it here again.

| Copied from `03-push-glasses-apart/` | Used by |
|---|---|
| `bench/bench.py`, `scoring.py`, `top_view.py`, `film.py` | the bench, through [`../bench/partners.py`](../bench/partners.py) |
| `01-one-fixed-nudge/plan.py` | solution 1, the geometry reference |
| `02-geometry-ranked/candidates.py`, `features.py`, `ranker.py` | solution 2 |
| `03-imitation-from-demonstrations/pictures.py`, `policy.py`, `train.py` | solution 3 |
| `05-smolvla-as-it-downloads/joining.py`, `policy.py` | solution 6 |
| `06-smolvla-fine-tuned/chunks.py`, `correction.py`, `train.py` | solution 6 |

Solution 2 also reads problem 3's fitted trees, `02-geometry-ranked/model/`,
and the rows they were fitted on, `02-geometry-ranked/data/`. Neither is kept
in git. Problem 3 makes both with `make train` in its `02-geometry-ranked`
folder, and they are copied here from there.
