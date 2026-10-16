"""Where the collected demonstrations are, and reading one of the sets back.

The sets live in [`../demonstrations`](../demonstrations), in a folder of their
own, because two solutions are fitted on them: this one and solution 6. This
module is the one page that knows where they are and how they are written, so
that both read them the same way and neither keeps a second copy of the layout.

A set is a LeRobot dataset, which is the format the borrowed models take. A
small model fitted from nothing wants something else: every demonstration in
memory at the size it reads, so a training step is a slice of an array rather
than a few hundred files off the disk. That is what ``load`` is for.

Shrinking the pictures on the way is the caller's to decide, and it is passed in
rather than chosen here. The sets are stored at the size the camera renders,
where a few thousand pictures are gigabytes, and each solution reads them at
whatever size its own model wants. Nothing here has an opinion about that, which
is what keeps it usable by both.

The action comes back as ``(frames, CHUNK, ACTION_WIDTH)``. It is stored flat,
one row a frame, for a reason ``collect.py`` gives, and this is where the shape
is put back.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from chunks import ACTION_WIDTH, CHUNK
from readings import CAMERA

HERE = Path(__file__).resolve().parent
DEMONSTRATIONS = HERE.parent / "demonstrations"

# The two sets: the one a model is fitted on, and the one held back to say how
# far the fit is from its teacher on pictures it never saw.
FITTING = DEMONSTRATIONS / "fitted-on"
HELD_BACK = DEMONSTRATIONS / "held-back"

# What was collected, for both sets, in one file beside them. One file rather
# than one inside each set, because everything inside a set is a few hundred
# megabytes of rendered pictures and is left out of git, while this is the
# measurement of what the collection did and belongs in it.
RECORD = DEMONSTRATIONS / "collected.json"

# What the sets are called in that record, and what LeRobot calls the dataset.
NAMES = {FITTING: "fitted-on", HELD_BACK: "held-back"}
REPO = "local/clear-the-table"

Shrink = Callable[[np.ndarray], np.ndarray]


def collected(root: Path | None = None) -> dict:
    """What ``collect.py`` wrote about the sets: their bands, their sizes and what they cost.

    With a set's folder, the part of the record about that set; without one, all
    of it.
    """
    record = json.loads(RECORD.read_text())
    return record if root is None else record[NAMES[root]]


def load(root: Path, shrink: Shrink | None = None, most: int | None = None) -> dict[str, np.ndarray]:
    """One collected set as arrays: pictures, states, actions and the episode each came from.

    ``shrink`` takes one picture and hands back a batch of one at the size the
    model reads; leave it out and the pictures come back at the size they were
    stored at. ``most`` caps how many frames are read, which is for a smoke test
    rather than for fitting: the first few hundred frames of a set are its first
    few tables.
    """
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    data = LeRobotDataset(repo_id=REPO, root=root)
    count = len(data) if most is None else min(most, len(data))
    if not count:
        raise ValueError(f"there are no demonstrations in {root}")

    # The size is taken from the first picture after shrinking rather than from a
    # constant, so that nothing here has to agree with the model's own size.
    first = _picture(data[0], shrink)
    pictures = np.empty((count, *first.shape), dtype=np.uint8)
    states = np.empty((count, len(data[0]["observation.state"])), dtype=np.float32)
    actions = np.empty((count, CHUNK, ACTION_WIDTH), dtype=np.float32)
    episodes = np.empty(count, dtype=np.int64)
    for i in range(count):
        frame = data[i]
        pictures[i] = _picture(frame, shrink)
        states[i] = frame["observation.state"].numpy()
        actions[i] = frame["action"].numpy().reshape(CHUNK, ACTION_WIDTH)
        episodes[i] = int(frame["episode_index"])
    return {"pictures": pictures, "states": states, "actions": actions, "episodes": episodes}


def _picture(frame: dict, shrink: Shrink | None) -> np.ndarray:
    """One frame's picture as the bench's own uint8 RGB, at the size the caller asked for.

    LeRobot hands a picture over as (colour, row, column) floats on 0 to 1, and
    everything either side of this module works in what the camera rendered.
    """
    picture = (frame[CAMERA].numpy().transpose(1, 2, 0) * 255.0).round().astype(np.uint8)
    return picture if shrink is None else shrink(picture)[0]
