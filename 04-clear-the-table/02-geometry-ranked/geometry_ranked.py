"""Solution 2: the geometry reference, with problem 3's fitted trees choosing among its pushes.

Solution 1 takes the one push problem 3's printed rule names: the shortest safe push that
gives a glass room. This solution lists every safe push on the table instead, scores each
one with problem 3's fitted trees, and makes the push with the best score. Everything else
is solution 1's: the same safe pushes, the same lengthening of a push that frees a glass,
the same fixed settings handed to MoveIt, the same glasses left out (those MoveIt refused,
and those that already have room), and the same rule for saying the table is done.
So the only difference between the two is which push is chosen, and comparing them
measures what the ordering is worth on the arm.

**The trees are problem 3's own fitted file, loaded and not fitted again.** If they were
fitted again here, a difference between problem 3's solution 2 and this one could be the
fit rather than the problem. Problem 3 makes the file with ``make train`` in its
``02-geometry-ranked`` folder, and an exact copy of it is kept in git in
``from-problem-3/``.

**Problem 3's files are loaded only for as long as they import each other.** They find
each other by short, general names such as ``table_and_push_encoding`` and ``ranker``, so they are put
under those names while their imports run, and taken out again afterwards. Each file keeps
hold of the modules it imported, so nothing is lost, and no other module asking for a
module of that name can be handed one of problem 3's by mistake.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from geometry_reference import SAFE, Geometry, arm_bench

from examiner.motion.push_motions import Settings
from examiner.simulation.taken_from_problem_3 import PUSHING

RANKED = PUSHING / "02-geometry-ranked"
RANKER = RANKED / "model" / "ranker.joblib"
# Problem 3's files, in the order they import each other.
FILES = ("candidates", "features", "ranker")


def _problem_three() -> dict[str, ModuleType]:
    """Problem 3's candidate list, inputs and ranker, loaded without displacing this problem's modules.

    They are loaded with the arm's top edge, as solution 1's planner is, so the list of safe
    pushes is solution 1's and the trees' input for tipping is measured at the arm's height.
    """
    displaced = {name: sys.modules.pop(name) for name in FILES if name in sys.modules}
    loaded: dict[str, ModuleType] = {}
    try:
        with arm_bench():
            for name in FILES:
                spec = importlib.util.spec_from_file_location(name, RANKED / f"{name}.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                loaded[name] = module
    finally:
        for name in FILES:
            sys.modules.pop(name, None)
        sys.modules.update(displaced)
    return loaded


_LOADED = _problem_three()
candidates, ranker = _LOADED["candidates"], _LOADED["ranker"]


def load_ranker(path=RANKER):
    """Problem 3's fitted trees, or a plain statement of what is missing."""
    if not path.exists():
        raise SystemExit(
            f"problem 3's fitted trees are not at {path}.\n"
            "The copy is kept in git, so restore it from there, or make them again in problem 3 -- "
            "`make train` in 03-push-glasses-apart/02-geometry-ranked -- copy its model/ folder to "
            "from-problem-3/02-geometry-ranked/, and run this again."
        )
    return ranker.Ranker.load(path)


class GeometryRanked(Geometry):
    """Solution 1, with the push chosen by problem 3's fitted trees instead of the printed rule."""

    name = "geometry ranked, fixed settings"

    def __init__(self, settings: Settings = SAFE, score=None) -> None:
        super().__init__(settings)
        # How a list of candidate pushes is scored: problem 3's trees, unless a test says otherwise.
        self.score = load_ranker() if score is None else score

    def choose(self, seen, skip):
        """The safe push with the best score, lengthened as solution 1 lengthens a push that frees a glass."""
        best, _, _ = ranker.ranked(seen, skip, self.score)
        if not best:
            return None
        pick = best[0]
        if not pick.freeing:
            return pick.push
        others = [o for o in seen if o.id != pick.glass.id]
        return self.lengthened(pick.glass, others, pick.push.heading, pick.push)
