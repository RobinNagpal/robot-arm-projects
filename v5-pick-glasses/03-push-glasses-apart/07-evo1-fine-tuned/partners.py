"""Everything this solution runs with and did not write, loaded rather than copied.

This solution asks one question only: does a newer and larger borrowed model
do better here than the 450M one solutions 5 and 6 use? A question of that
shape is answerable only while everything else is held still, so nothing that
the other folders already settle is written again here.

**Solution 5** settles how a borrowed model's numbers are read as jaw
waypoints, through its ``joining.py``, and how a table is cleared push by
push, through its ``clear.py``. Both are imported. A second copy of either
would be a second thing that could differ between this solution and the two
it is compared with.

**Solution 6** settles the demonstrations. Its ``demonstrations/`` holds the
teacher's pushes on tables 1000 onwards, already written in the convention
above, and this solution is fitted on that very dataset rather than on a
fresh collection of its own. Using the same file is stronger than using the
same recipe, because it removes even the simulator's own randomness from the
difference between the two results.

**Solution 2** is the teacher those demonstrations are of, and **solution 1**
holds the tipping limit every solution shares.

**Solution 6's own modules are deliberately not imported.** They import a
module called ``partners`` themselves, meaning their own, and this folder's
file of that name would answer instead. So what this solution needs from that
folder it reads from the dataset rather than from the code: how many waypoints
a chunk holds and how wide a waypoint is are written in the dataset's own
description of itself, which is the honest place to read them from in any
case, because the dataset is what the fitting actually sees.

None of those folders is a package, because every one of their names starts
with a digit, so they join the import path instead. Solution 5's goes on the
end of the path rather than the front, because it has a ``run.py`` of its own
and this folder's has to win.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROBLEM = Path(__file__).resolve().parent.parent
GEOMETRY = PROBLEM / "01-one-fixed-nudge"
RANKED = PROBLEM / "02-geometry-ranked"
DOWNLOADED = PROBLEM / "05-smolvla-as-it-downloads"
FINE_TUNED = PROBLEM / "06-smolvla-fine-tuned"

# Solution 6's demonstration sets, used as they are. See the module docstring:
# the same file, not the same recipe.
FITTING = FINE_TUNED / "demonstrations"
TUNING = FINE_TUNED / "demonstrations-check"
# LeRobot wants a dataset name beside the folder. It is a label and not a
# place: the folder above is where the data really is. This is the name
# solution 6 writes, and it has to match or the library looks on the Hub.
REPO = "local/push-glasses-apart"

for _folder in (GEOMETRY, RANKED):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))
for _folder in (DOWNLOADED, FINE_TUNED):
    if str(_folder) not in sys.path:
        sys.path.append(str(_folder))

from clear import TAKE_MARGIN, Tally, clear, jaw_now  # noqa: E402
from joining import (  # noqa: E402
    ACTION_SPAN,
    INSTRUCTION,
    SLOTS,
    UP_HIGHER,
    chunk_for,
    hits_refused,
    nearest,
    to_jaw,
    to_state,
)
from policy import CAMERA, Downloaded, device_for  # noqa: E402


def described(root: Path = FITTING) -> dict:
    """What the demonstration set says about itself: its name and its shapes.

    Read from the dataset instead of imported from solution 6 for the reason
    the docstring above gives, and it is the better source anyway: a fit is
    only correct for the chunks it was really given.
    """
    info = root / "meta" / "info.json"
    if not info.exists():
        raise FileNotFoundError(
            f"no demonstrations at {root}. Make them with "
            "`pixi run python 06-smolvla-fine-tuned/demonstrations.py`."
        )
    facts = json.loads(info.read_text())
    wide = int(facts["features"]["action"]["shape"][0])
    if wide % SLOTS:
        raise ValueError(f"a chunk of {wide} numbers does not divide into waypoints of {SLOTS}")
    return {
        "chunk": wide // SLOTS,
        "slots": SLOTS,
        "demonstrations": int(facts["total_frames"]),
        "tables": int(facts["total_episodes"]),
    }


__all__ = [
    "ACTION_SPAN",
    "CAMERA",
    "DOWNLOADED",
    "FINE_TUNED",
    "FITTING",
    "GEOMETRY",
    "INSTRUCTION",
    "PROBLEM",
    "RANKED",
    "REPO",
    "SLOTS",
    "TAKE_MARGIN",
    "TUNING",
    "UP_HIGHER",
    "Downloaded",
    "Tally",
    "chunk_for",
    "clear",
    "described",
    "device_for",
    "hits_refused",
    "jaw_now",
    "nearest",
    "to_jaw",
    "to_state",
]
