"""The two folders this solution is built out of, loaded in one place.

This solution is a port, and almost all of it already exists. Two folders hold
it:

* ``04-clear-the-table/01-one-fixed-nudge`` -- problem 4's geometry reference.
  The whole loop comes from there: where to stand to see the table, what has
  been seen, a push written out as waypoints, the ranging push that finds how
  far away a glass is, the test push, and the rule for saying "done".
* ``03-push-glasses-apart/02-geometry-ranked`` -- problem 3's ranked solution.
  The candidate set, the eight inputs and the fitted trees come from there.

Neither folder can be imported by name, because both names start with a digit
and so neither is a package. ``partners.py`` solves that for problem 3's
solution 1 by putting its folder on ``sys.path``, and that works there because
nothing needed from it shares a name with anything here. It would not work
here: both folders bring a ``run``-shaped script and a ``test_`` file with
them, and problem 3's solution 2 in particular would put its own ``candidates``
beside this folder's files and let the winner depend on where pytest started.
Problem 3's solution 2 had the same problem reaching problem 3's solution 1 and
solved it this way, so the pattern is its own: load the file, register it under
the plain name its siblings import it by, and leave the folders off the path.

The registration under the plain name is not decoration. ``jaw_paths`` says
``from tour import Stand``, ``features`` says ``from candidates import nudge``:
those imports are resolved out of ``sys.modules``, so the names have to be the
ones the files already use. Loading in dependency order is what makes that
work.

A module pytest has already imported from one of those folders is used as it
is, rather than loaded a second time. Two copies of ``nudge`` would be two
classes, and an ``isinstance`` check or a patched constant would then be true
of one and not the other.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import partners

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "01-one-fixed-nudge"  # problem 4's geometry reference
RANKED = partners.PUSHING / "02-geometry-ranked"  # problem 3's ranked solution

# The fitted trees themselves. Problem 3's own file, not a refit: the whole
# point of this solution is that the only difference between problem 3's
# solution 2 and this one is the problem. ``model/`` is not in git -- problem 3
# regenerates it with ``make train`` -- so this can be missing, and
# ``ranked.py`` says so plainly rather than failing on a pickle.
RANKER = RANKED / "model" / "ranker.joblib"
# The rows the trees were fitted on. Nothing at run time needs them; a check
# that the inputs this problem hands the trees still land where those rows do
# needs them, and one of the eight did not. See ``measure.py --inputs``.
ROWS = RANKED / "data" / "rows.npz"


def _module(name: str, path: Path) -> ModuleType:
    """One file, loaded under the name its siblings import it by."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed, so that a module it imports which
    # imports it back finds it half-built rather than looping.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Problem 4's geometry reference, in the order its files import each other.
tour = _module("tour", REFERENCE / "tour.py")
remembered = _module("remembered", REFERENCE / "remembered.py")
jaw_paths = _module("jaw_paths", REFERENCE / "jaw_paths.py")
nudge = _module("nudge", REFERENCE / "nudge.py")

# Problem 3's ranked solution, in the same way.
candidates = _module("candidates", RANKED / "candidates.py")
features = _module("features", RANKED / "features.py")
ranker = _module("ranker", RANKED / "ranker.py")

__all__ = [
    "RANKED",
    "RANKER",
    "ROWS",
    "REFERENCE",
    "candidates",
    "features",
    "jaw_paths",
    "nudge",
    "ranker",
    "remembered",
    "tour",
]
