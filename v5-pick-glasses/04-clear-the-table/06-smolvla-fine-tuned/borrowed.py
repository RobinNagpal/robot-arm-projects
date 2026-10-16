"""Everything this solution runs with and did not write, loaded in one place.

This solution is [solution 5](../05-smolvla-as-it-downloads) with a correction
fitted on problem 4's own demonstrations. Almost nothing about it is new, so
almost nothing here is new either, and the whole debt is on this one page.

Three folders are involved.

**Problem 4's solution 5**, which is this solution's matched partner. Its
``as_downloaded.py`` is the model sat in problem 4's conversation: the picture
from the camera on the arm goes in, a path for the jaw comes out, and
``bench/stopping.py`` reads the declaration that a table is finished out of the
shape of the answers. ``fine_tuned.py`` subclasses that rather than writing a
second copy of it, because the pair is only clean while everything but the
weights is the same code.

**Problem 3's solution 5**, which solution 5 here already borrows: ``joining.py``
is how six numbers of somebody else's arm become jaw waypoints, and ``policy.py``
is loading ``lerobot/smolvla_base`` and asking it. Holding ``joining.py`` still
is the point. If problem 4 re-chose the box the model's output maps onto, a
difference between the two problems would be a difference between two joins.

**Problem 3's solution 6**, which is the same fit in the problem next door:
``correction.py`` is where the correction goes and how the corrected model is
loaded, and ``train.py`` is the fitting recipe. Both are imported so that the
two problems' fits differ in their problem and their data and in nothing that
could be mistaken for a result.

**And problem 4's solution 3**, for the demonstrations. ``loading.py`` is where
the collected sets are and how a set is read back, ``chunks.py`` says what a
stored action is, and ``readings.py`` says what a stored observation is. The two
fitted solutions read one set of demonstrations through one reader, which is why
the set sits in a folder of its own.

**Nothing is put on ``sys.path``, which is deliberate.** Problem 4's brief warns
that problem 3 has modules named ``scoring``, ``clock`` and ``partners`` as well,
and that problem 4's own have to win. Appending problem 3's solution folders
would also bring their ``run.py``, ``clear.py`` and ``borrowed.py`` alongside
this folder's, and then an import would depend on where pytest was started. So
every borrowed file is loaded from its own path and registered under the plain
name its siblings import it by, which is the pattern solution 5 and
``03-imitation-from-demonstrations/wiring.py`` both use.

Registering under the plain name is not decoration. ``policy.py`` says
``from joining import ...`` and ``loading.py`` says ``from chunks import ...``,
both resolved out of ``sys.modules``, so those two names have to be taken by
these files and taken before the file that imports them is read.
"""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import partners

HERE = Path(__file__).resolve().parent
PROBLEM = HERE.parent
# The demonstrations, and the solution that collected them.
IMITATION = PROBLEM / "03-imitation-from-demonstrations"
# The same model with nothing fitted, in this problem and in problem 3.
DOWNLOADS = PROBLEM / "05-smolvla-as-it-downloads"
PUSHING_DOWNLOADS = partners.PUSHING / "05-smolvla-as-it-downloads"
# The same fit, in the problem next door.
PUSHING_FITTED = partners.PUSHING / "06-smolvla-fine-tuned"

# How many waypoints the borrowed model emits in one pass. It is SmolVLA's own
# ``chunk_size`` and not a number chosen here: ``correction.borrowed()`` reads
# the loaded configuration and raises if the two disagree, which is what keeps
# this honest. It is written down because two borrowed files ask for it under
# the name ``chunks.CHUNK``, and in problem 4 that name is already taken by the
# two hundred rows a demonstration is *stored* in.
MODEL_CHUNK = 50


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


@contextmanager
def _standing_in(**modules: dict):
    """Put up a module of names, load a borrowed file, and take the module down again.

    Problem 3's solution 6 reads three names out of *its* ``partners`` and one
    out of *its* ``chunks`` while it is being imported, and problem 4 has a
    module of each of those names already, holding different things. So a
    stand-in is put up for the moment the borrowed file is read and removed
    straight afterwards. Leaving it up would mean that everything importing
    ``partners`` after this point got five names instead of the bench's forty,
    silently.

    ``03-imitation-from-demonstrations/wiring.py`` does the same thing for the
    same reason, and the alternative in both places was to copy the borrowed
    file, which is the one thing these folders exist not to do.
    """
    was = {name: sys.modules.get(name) for name in modules}
    for name, names in modules.items():
        stand_in = ModuleType(name)
        stand_in.__dict__.update(names)
        sys.modules[name] = stand_in
    try:
        yield
    finally:
        for name, before in was.items():
            if before is None:
                del sys.modules[name]
            else:
                sys.modules[name] = before


# Problem 4's own demonstration modules first, under the names they import each
# other by. Loaded through ``_module`` rather than imported, so that the order
# this depends on is written here instead of being a side effect of the import
# sorter.
chunks = _module("chunks", IMITATION / "chunks.py")
readings = _module("readings", IMITATION / "readings.py")
loading = _module("loading", IMITATION / "loading.py")

# Then the join and the model, in dependency order: policy.py imports joining.
joining = _module("joining", PUSHING_DOWNLOADS / "joining.py")
policy = _module("policy", PUSHING_DOWNLOADS / "policy.py")

# Then the partner, which reads ``joining`` off this module while this module is
# still being executed. That works because the line above has already set the
# attribute, and because Python registers a module before it finishes running it.
as_downloaded = _module("as_downloaded", DOWNLOADS / "as_downloaded.py")

# And last the fit next door, which needs the stand-ins.
with _standing_in(
    chunks={"CHUNK": MODEL_CHUNK},
    partners={
        "CAMERA": policy.CAMERA,
        "SLOTS": joining.SLOTS,
        "WEIGHTS": policy.WEIGHTS,
        "device_for": policy.device_for,
        "to_jaw": joining.to_jaw,
        "to_state": joining.to_state,
    },
    demonstrations={
        "FITTING": loading.FITTING,
        "TUNING": loading.HELD_BACK,
        "REPO": loading.REPO,
    },
):
    # Problem 3's solution 6 reads a recorded push into the model's convention.
    # ``resampled``, ``as_action`` and ``drift`` are the three pieces of that
    # which are arithmetic rather than problem 3's own recording, and
    # ``targets.py`` uses them. Loaded under a name of its own because
    # ``chunks`` means problem 4's chunk here.
    pushing_chunks = _module("pushing_chunks", PUSHING_FITTED / "chunks.py")
    # Where the correction goes, and the corrected model.
    correction = _module("correction", PUSHING_FITTED / "correction.py")
    # The fitting recipe: the step count, the rate and its warm-up, the batch,
    # the pre-processing of a batch and the distance from the teacher in
    # millimetres. Its ``main`` is never called; ``train.py`` here fits three
    # seeds and reads problem 4's demonstrations, so the loop is written there.
    fitting = _module("fitting", PUSHING_FITTED / "train.py")

# ``correction.CORRECTION`` and ``fitting``'s own default point at problem 3's
# folder, because that is where those files live. Nothing here ever uses either:
# a fit of problem 4 that quietly loaded problem 3's correction would be a
# measurement of the wrong thing and would look exactly like a measurement of
# the right one. ``weights.py`` is the only place this folder names a folder of
# weights, and it is always passed explicitly.

__all__ = [
    "DOWNLOADS",
    "IMITATION",
    "MODEL_CHUNK",
    "PUSHING_DOWNLOADS",
    "PUSHING_FITTED",
    "as_downloaded",
    "chunks",
    "correction",
    "fitting",
    "joining",
    "loading",
    "policy",
    "pushing_chunks",
    "readings",
]
