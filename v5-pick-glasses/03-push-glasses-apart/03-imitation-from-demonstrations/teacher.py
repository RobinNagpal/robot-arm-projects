"""Solution 2, loaded so this folder can run it and watch what the jaw did.

The teacher is not written here. It is ``../02-geometry-ranked``, run
unchanged: the same candidate geometry, the same fitted ranker, the same
loop. This module only makes it importable, and the reason that needs a
module at all is a name clash. Solutions 1, 2 and 4 each have a ``run.py``,
solution 1 has a ``plan.py``, and solution 2's ``candidates.py`` puts
solution 1's folder at the front of the path when it is imported. So a plain
``import run`` afterwards gives solution 1's runner. Loading solution 2's
runner from its own file settles which one it is.

The same path setup gives this folder ``nudge``, solution 1's geometry, which
is where the shared tipping limit lives. Solution 3 uses that limit and
nothing else from it: the limit is a gate in front of the policy, not part of
the policy.

Solution 2 has to be fitted before it can teach::

    pixi run python 02-geometry-ranked/train.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROBLEM = Path(__file__).resolve().parent.parent
GEOMETRY = PROBLEM / "01-one-fixed-nudge"
RANKED = PROBLEM / "02-geometry-ranked"

# Appended, never put at the front: this folder has a ``train.py`` and a
# ``run.py`` of its own, and so do its neighbours.
for folder in (GEOMETRY, RANKED):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

import plan as nudge  # noqa: E402  solution 1's geometry; the tipping limit is shared

__all__ = ["RANKED", "clear", "nudge", "pick_pushes"]

_runner: ModuleType | None = None


def _ranked_run() -> ModuleType:
    global _runner
    if _runner is None:
        spec = importlib.util.spec_from_file_location("ranked_run", RANKED / "run.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["ranked_run"] = module
        spec.loader.exec_module(module)
        _runner = module
    return _runner


def pick_pushes():
    """Solution 2's own chooser: the geometry's candidates, ranked, best first.

    Raises if the ranker has not been fitted rather than falling back to the
    printed rule, because the two teach different things and a demonstration
    set should say which teacher made it.
    """
    import ranker

    if not ranker.MODEL.exists():
        raise FileNotFoundError(
            f"no teacher: {ranker.MODEL} is missing. Fit it with "
            f"`pixi run python 02-geometry-ranked/train.py`."
        )
    return _ranked_run().by_model(ranker.Ranker.load())


def clear(table, pick, watch=None) -> dict[int, str]:
    """Solution 2's loop over one table, unchanged. Returns what it refused, and why."""
    return _ranked_run().clear(table, pick, watch=watch)
