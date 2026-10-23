"""The folder this solution is built out of, loaded in one place.

Almost all of this solution already exists. Problem 4's geometry reference,
``04-clear-the-table/01-one-fixed-nudge``, holds every part of the job that is
about *seeing* rather than about choosing: where to stand to look at the table,
what has been seen so far, a push written out as waypoints for the jaw, and
the rule for when a table may be declared finished. All of that is the same
work whoever picks the push, and the reference says so itself -- ``_choose`` is
a method there and not a call written into the loop, "because the next solution
in this problem is this same loop with a different chooser".

This solution is that different chooser.

The reference cannot be imported by name: its folder name starts with a digit,
so it is not a package. ``partners.py`` puts problem 3's solution 1 on
``sys.path`` and that is safe there, but it is not a pattern to repeat for a
second folder -- the reference brings a ``conftest.py``, a ``calibrate.py`` and
a ``test_`` file with it, and which copy of a name won would then depend on
where pytest was started. So each file is loaded from its path and registered
under the plain name its siblings import it by. Problem 4's solution 2 does the
same thing for the same reason; the pattern is problem 3's solution 2's own.

Registering under the plain name is not decoration. ``jaw_paths`` says ``from
tour import Stand`` and ``nudge`` says ``from remembered import Remembered``,
and those are resolved out of ``sys.modules``, so loading in dependency order
is what makes them work.

**Nothing of problem 3's solution 4 is loaded here, and that is deliberate.**
Its ``features`` and ``model`` were read closely and this folder's ``encoding``
and ``push_model`` are written from them, but they could not be borrowed. Two
things in them are about problem 3's hand-over rather than about forward
models: the push it encodes is one problem 3's simulator feels its way into, so the
distance to the glass is not part of it, and the table's one glass kind is an
input, which problem 4's contract does not hand over. Loading it and then
overriding both would leave a module whose every field meant something slightly
different from its name.

The names here avoid ``features`` and ``model`` on purpose. Problem 4's
solution 2 registers problem 3's ranked ``features`` under that very name, and
two different modules under one name in ``sys.modules`` is a bug that only
appears when somebody runs the two folders' tests together.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import partners

import plan

HERE = Path(__file__).resolve().parent
# Problem 4's geometry reference, named off ``partners`` rather than off this
# file's own parent. Importing ``partners`` is also what has to happen before
# ``plan`` above can be imported at all -- it is what puts problem 3's solution
# 1 on the path -- so taking the folder from it keeps the two facts together
# instead of leaving an import that looks unused and gets tidied away.
REFERENCE = partners.PROBLEM / "01-one-fixed-nudge"

# Where the collected pushes and the fitted networks go. Neither is in git:
# both are made again by ``make collect`` and ``make train``.
DATA = HERE / "data"
WEIGHTS = HERE / "weights"


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


# The reference's files, in the order they import each other.
tour = _module("tour", REFERENCE / "tour.py")
remembered = _module("remembered", REFERENCE / "remembered.py")
jaw_paths = _module("jaw_paths", REFERENCE / "jaw_paths.py")
nudge = _module("nudge", REFERENCE / "nudge.py")

# ``plan`` above is problem 3's geometry, which ``partners`` puts on the path
# and the reference imports under that name. It is imported here as well, and
# last, so that a reader can see the whole debt on one page: the import sorter
# files it below ``partners``, which is the order it has to be read in.

__all__ = [
    "DATA",
    "REFERENCE",
    "WEIGHTS",
    "jaw_paths",
    "nudge",
    "plan",
    "remembered",
    "tour",
]
