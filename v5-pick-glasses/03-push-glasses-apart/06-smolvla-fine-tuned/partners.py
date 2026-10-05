"""Everything this solution runs with and did not write, loaded rather than copied.

Three other folders are involved, and each is here for a reason
[the document](../../docs/03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md)
gives.

**Solution 5**, which is this solution's matched partner. Its ``joining.py``
is the reading that turns the model's actions into jaw waypoints, and its
``clear.py`` is the loop of plan, feel and look again. The document's whole
argument is that nothing varies between the two halves of the pair except the
training, so a second copy of either here would be a second thing that could
vary. They are imported for that reason and not for convenience.

**Solution 2**, the teacher. Its pushes are this solution's training set, so
it is run unchanged: the demonstrations are of solution 2 and not of something
this folder rewrote.

**Solution 1's geometry**, for the tipping limit, which is the same arithmetic
in all six solutions.

None of those folders is a package, because every one of their names starts
with a digit, so they join the import path instead. Solution 5's goes on the
end of it rather than the front, because it holds a ``run.py`` of its own and
this folder's has to win.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROBLEM = Path(__file__).resolve().parent.parent
GEOMETRY = PROBLEM / "01-one-fixed-nudge"
RANKED = PROBLEM / "02-geometry-ranked"
DOWNLOADED = PROBLEM / "05-smolvla-as-it-downloads"

for _folder in (GEOMETRY, RANKED):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))
if str(DOWNLOADED) not in sys.path:
    sys.path.append(str(DOWNLOADED))

import plan as nudge  # noqa: E402
from clear import TAKE_MARGIN, Tally, clear, jaw_now  # noqa: E402
from joining import (  # noqa: E402
    ACTION_SPAN,
    INSTRUCTION,
    SLOTS,
    chunk_for,
    hits_refused,
    nearest,
    to_jaw,
    to_state,
)
from policy import CAMERA, WEIGHTS, device_for  # noqa: E402

__all__ = [
    "ACTION_SPAN",
    "CAMERA",
    "DOWNLOADED",
    "GEOMETRY",
    "INSTRUCTION",
    "PROBLEM",
    "RANKED",
    "SLOTS",
    "TAKE_MARGIN",
    "WEIGHTS",
    "Tally",
    "chunk_for",
    "clear",
    "device_for",
    "hits_refused",
    "jaw_now",
    "nearest",
    "nudge",
    "taught",
    "teacher",
    "to_jaw",
    "to_state",
]

_ranked: ModuleType | None = None


def _runner() -> ModuleType:
    """Solution 2's ``run.py``, loaded from its own path.

    Solutions 1, 2 and 4 each have a ``run.py``, and importing solution 2's
    candidates puts solution 1's folder at the front of the path, so a bare
    ``import run`` afterwards is a coin toss. Loading it by path settles which
    one it is.
    """
    global _ranked
    if _ranked is None:
        spec = importlib.util.spec_from_file_location("ranked_run", RANKED / "run.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["ranked_run"] = module
        spec.loader.exec_module(module)
        _ranked = module
    return _ranked


def teacher():
    """Solution 2's own chooser: its geometry's candidates, ranked by its fitted model.

    Raises if the ranker has not been fitted rather than quietly falling back
    to the printed rule, because the two teach different things and a
    demonstration set has to say which teacher made it.
    """
    import ranker

    if not ranker.MODEL.exists():
        raise FileNotFoundError(
            f"no teacher: {ranker.MODEL} is missing. Fit it with "
            "`pixi run python 02-geometry-ranked/train.py`."
        )
    return _runner().by_model(ranker.Ranker.load())


def taught(table, pick, watch=None) -> dict[int, str]:
    """Solution 2's loop over one table, unchanged. Returns what it refused, and why."""
    return _runner().clear(table, pick, watch=watch)
