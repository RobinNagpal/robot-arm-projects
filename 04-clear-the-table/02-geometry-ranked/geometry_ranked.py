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

from geometry_reference import SAFE_SETTINGS, GeometryReference, problem_3_files_see_the_arm_top_edge

from examiner.motion.push_motions import MoveItSettings
from examiner.simulation.taken_from_problem_3 import PUSHING

PROBLEM_3_RANKED_FOLDER = PUSHING / "02-geometry-ranked"
RANKER_FILE = PROBLEM_3_RANKED_FOLDER / "model" / "ranker.joblib"
# Problem 3's files, in the order they import each other.
PROBLEM_3_FILES_IN_IMPORT_ORDER = ("candidates", "features", "ranker")


def _load_problem_3_ranked_files() -> dict[str, ModuleType]:
    """Problem 3's candidate list, inputs and ranker, loaded without displacing this problem's modules.

    They are loaded with the arm's top edge, as solution 1's planner is, so the list of safe
    pushes is solution 1's and the trees' input for tipping is measured at the arm's height.
    """
    displaced = {
        name: sys.modules.pop(name) for name in PROBLEM_3_FILES_IN_IMPORT_ORDER if name in sys.modules
    }
    loaded: dict[str, ModuleType] = {}
    try:
        with problem_3_files_see_the_arm_top_edge():
            for name in PROBLEM_3_FILES_IN_IMPORT_ORDER:
                spec = importlib.util.spec_from_file_location(name, PROBLEM_3_RANKED_FOLDER / f"{name}.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                loaded[name] = module
    finally:
        for name in PROBLEM_3_FILES_IN_IMPORT_ORDER:
            sys.modules.pop(name, None)
        sys.modules.update(displaced)
    return loaded


_PROBLEM_3_MODULES = _load_problem_3_ranked_files()
candidates, ranker = _PROBLEM_3_MODULES["candidates"], _PROBLEM_3_MODULES["ranker"]


def load_problem_3_trees(ranker_file=RANKER_FILE):
    """Problem 3's fitted trees, or a plain statement of what is missing."""
    if not ranker_file.exists():
        raise SystemExit(
            f"problem 3's fitted trees are not at {ranker_file}.\n"
            "The copy is kept in git, so restore it from there, or make them again in problem 3 -- "
            "`make train` in 03-push-glasses-apart/02-geometry-ranked -- copy its model/ folder to "
            "from-problem-3/02-geometry-ranked/, and run this again."
        )
    return ranker.Ranker.load(ranker_file)


class GeometryRanked(GeometryReference):
    """Solution 1, with the push chosen by problem 3's fitted trees instead of the printed rule."""

    name = "geometry ranked, fixed settings"

    def __init__(self, settings: MoveItSettings = SAFE_SETTINGS, score_candidate_pushes=None) -> None:
        super().__init__(settings)
        # How a list of candidate pushes is scored: problem 3's trees, unless a test says otherwise.
        self.score_candidate_pushes = (
            load_problem_3_trees() if score_candidate_pushes is None else score_candidate_pushes
        )

    def choose_push(self, readings, glasses_to_skip):
        """The safe push with the best score, lengthened as solution 1 lengthens a push that frees a glass."""
        ranked_pushes, _, _ = ranker.ranked(readings, glasses_to_skip, self.score_candidate_pushes)
        if not ranked_pushes:
            return None
        best_push = ranked_pushes[0]
        if not best_push.freeing:
            return best_push.push
        others = [other for other in readings if other.id != best_push.glass.id]
        return self.lengthened_push(best_push.glass, others, best_push.push.heading, best_push.push)
