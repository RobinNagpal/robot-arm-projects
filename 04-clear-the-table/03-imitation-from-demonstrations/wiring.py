"""Problem 3's chunked policy, loaded from this problem's copy of it in ``from-problem-3/``.

The file is called ``wiring`` and not ``borrowed``, which is the name the other
solutions in this problem give the same job, and the reason is mechanical.
``collect.py`` runs solution 2, and solution 2's own ``borrowed`` has to be the
one *its* files find, so its folder goes to the front of the import path and its
``borrowed`` takes that name in ``sys.modules`` for the rest of the process. Two
files called ``borrowed`` in one process is one too many, and the one that would
quietly lose is this one.

This solution's own files sit beside this one: ``chunks`` says what a chunk is,
``readings`` what the model is told about the table, ``loading`` where the
demonstrations are, and ``collect`` is what made them. What is *not* written
here is the model, the scaling and the fitting loop. Those are problem 3's
[solution 3](../../03-push-glasses-apart/03-imitation-from-demonstrations), and
they are borrowed for one reason: the two problems exist to be compared, so if
the wiring were written again a difference between problem 3's solution 3 and
this one could be the wiring rather than the problem.

That folder's name starts with a digit, so it cannot be imported by name. Each
file is loaded from its path and registered under the plain name its siblings
import it by -- the pattern ``02-geometry-ranked/borrowed.py`` uses, and for the
same reason. Order matters, because those imports are resolved out of
``sys.modules``: ``policy`` says ``from chunks import ACTION_WIDTH, CHUNK``, and
it is *this* folder's ``chunks`` it has to find. Registering this folder's own
modules first is what makes sure of it.

``pictures`` is borrowed too. It is the size a picture is read at, and sharing it
means the two problems' students see a picture at the same size.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import partners

HERE = Path(__file__).resolve().parent
CLONING = partners.PUSHING / "03-imitation-from-demonstrations"


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


def _with_a_stand_in(name: str, path: Path, stand_in: str, **names) -> ModuleType:
    """Load a borrowed file that imports a module this folder does not have.

    Problem 3's ``train`` reads two paths out of *its* ``collect`` at import
    time, so a module of that name has to exist for the import to work. This
    folder has a ``collect`` of its own and it is a different file, so the
    stand-in is put up only while the borrowed file is being read and taken down
    straight afterwards. Leaving it up would mean that anything importing
    ``collect`` after this point got the stand-in instead, silently.

    The names in it are never read: this folder calls ``fit`` and nothing else,
    never ``main``, which is where those paths are used. The alternative was to
    copy the fitting loop, which is the one thing this file exists not to do.
    """
    was = sys.modules.get(stand_in)
    module = ModuleType(stand_in)
    module.__dict__.update(names)
    sys.modules[stand_in] = module
    try:
        return _module(name, path)
    finally:
        if was is None:
            del sys.modules[stand_in]
        else:
            sys.modules[stand_in] = was


# This folder's own modules first, under the names the borrowed files import
# them by, so that problem 3's wiring reads problem 4's chunk and not its own.
# Loaded through ``_module`` rather than imported, so that the order this
# depends on is written down here instead of being a side effect of the import
# sorter.
chunks = _module("chunks", HERE / "chunks.py")
readings = _module("readings", HERE / "readings.py")
loading = _module("loading", HERE / "loading.py")

pictures = _module("pictures", CLONING / "pictures.py")
policy = _module("policy", CLONING / "policy.py")
fitting = _with_a_stand_in(
    "fitting", CLONING / "train.py", "collect", DEMOS=loading.FITTING, CHECK=loading.HELD_BACK
)

__all__ = ["CLONING", "chunks", "fitting", "loading", "pictures", "policy", "readings"]
