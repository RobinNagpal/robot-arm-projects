"""The two files this solution is built out of, loaded in one place.

Almost nothing here is new. The model, and the whole join between what it
emits and what this cell's jaw is, already exist in
``03-push-glasses-apart/05-smolvla-as-it-downloads``:

* ``joining.py`` -- how six numbers of somebody else's arm become jaw
  waypoints, and how the jaw's pose becomes the model's state input. Every
  number in it is read off the checkpoint or off the cell, and nothing in it
  is fitted, so it is the same join in both problems. **Holding it still is
  the point.** If problem 4 re-chose the box the model's output maps onto, a
  difference between the two problems would be a difference between two joins
  and would say nothing about the wrist camera.
* ``policy.py`` -- loading ``lerobot/smolvla_base`` and asking it.

Neither folder can be imported by name, because its name starts with a digit
and so it is not a package. Problem 4's ``partners.py`` solves that for
problem 3's solution 1 by putting its folder on ``sys.path``, and that works
there because nothing needed from it shares a name with anything here. It
would not work here. Problem 3's solution 5 carries a ``run.py``, a
``clear.py`` and a ``test_`` file of its own, and putting its folder on the
path would let those sit beside this folder's files and let an import depend
on where pytest was started. So this follows problem 4's solution 2 instead:
load the file, register it under the plain name its siblings import it by, and
leave the folder off the path.

The registration under the plain name is not decoration. ``policy.py`` says
``from joining import ...``, which is resolved out of ``sys.modules``, so
``joining`` has to be loaded under exactly that name and loaded first.

What is **not** borrowed from problem 3's solution 5 is ``clear.py``. Its loop
is problem 3's: it racks every glass that has room, counts pushes against a
push budget, and refuses a path that would reach a tipping glass. Problem 4
racks nothing, has no push budget, and keeps the tipping refusal in the cell
itself, so there is nothing of that file left to borrow. ``as_downloaded.py``
is the replacement, and it is the only new thinking in this folder.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import partners

HERE = Path(__file__).resolve().parent
# The same solution in problem 3, which is what this one is a port of.
DOWNLOADS = partners.PUSHING / "05-smolvla-as-it-downloads"


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


# In dependency order: policy.py imports joining by its plain name.
joining = _module("joining", DOWNLOADS / "joining.py")
policy = _module("policy", DOWNLOADS / "policy.py")

__all__ = ["DOWNLOADS", "joining", "policy"]
