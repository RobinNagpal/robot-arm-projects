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
import readings
from chunks import ACTION_WIDTH, CHUNK
from readings import CAMERA
from work_cell.table.layout import TABLE_CENTRE_XY

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


def load(
    root: Path,
    shrink: Shrink | None = None,
    most: int | None = None,
    looks: int | None = None,
) -> dict[str, np.ndarray]:
    """One collected set as arrays: pictures, states, actions, decisions and episodes.

    ``gate`` is what the teacher decided on each frame, as two numbers: which of
    the four kinds of answer it gave, and which slot the glass it aimed at sits
    in. It is what ``gate.py`` is fitted on, and it is also how ``train.py``
    tells a push from a look when it balances the mixture.

    ``aimed_at`` is where the glass that answer was aimed at stood, or the middle
    of the table where it was aimed at none. The actions themselves are stored in
    the cell's own numbers, because that is what the teacher really did and
    because solution 6 reads the same set; a reader that wants a push measured
    from its own glass subtracts this.

    ``shrink`` takes one picture and hands back a batch of one at the size the
    model reads; leave it out and the pictures come back at the size they were
    stored at. ``most`` caps how many frames are read, which is for a smoke test
    rather than for fitting: the first few hundred frames of a set are its first
    few tables.

    ``looks`` caps how many *looking* frames are read, and it is for fitting
    rather than for a smoke test. A set collected from three times as many
    tables holds three times as many looks, and a look is the one kind of answer
    a fit already has far more of than it can use: ``train.balanced`` throws most
    of them away again before a single step is taken. Reading them all costs a
    gigabyte of memory and several minutes a run for frames no step will ever
    see. Every answer that touches a glass is kept whatever the cap, because
    those are the scarce ones, and the frames are chosen with a fixed seed so
    that two runs read the same set.

    The cap changes the mixture, so a model that has to learn how often each
    kind of answer really happens -- the gate -- must be fitted without it.
    """
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    data = LeRobotDataset(repo_id=REPO, root=root)
    if not len(data):
        raise ValueError(f"there are no demonstrations in {root}")
    rows = to_read(kinds_of(data), most, looks)
    count = len(rows)

    # The size is taken from the first picture after shrinking rather than from a
    # constant, so that nothing here has to agree with the model's own size.
    first = _picture(data[0], shrink)
    pictures = np.empty((count, *first.shape), dtype=np.uint8)
    states = np.empty((count, len(data[0]["observation.state"])), dtype=np.float32)
    actions = np.empty((count, CHUNK, ACTION_WIDTH), dtype=np.float32)
    episodes = np.empty(count, dtype=np.int64)
    decisions = np.empty((count, 2), dtype=np.int64)
    shoves = np.empty((count, readings.SHOVE_WIDTH), dtype=np.float32)
    for i, row in enumerate(rows):
        frame = data[int(row)]
        pictures[i] = _picture(frame, shrink)
        states[i] = frame["observation.state"].numpy()
        actions[i] = frame["action"].numpy().reshape(CHUNK, ACTION_WIDTH)
        episodes[i] = int(frame["episode_index"])
        decisions[i] = frame["gate"].numpy().round().astype(np.int64)
        shoves[i] = frame["shoves"].numpy()
    return {
        "pictures": pictures,
        "states": states,
        "actions": actions,
        "episodes": episodes,
        "gate": decisions,
        "shoves": shoves,
        "aimed_at": np.array([aimed_at(row) for row in states], dtype=np.float32),
    }


def kinds_of(data) -> np.ndarray:
    """Which kind of answer every frame in a set holds, without reading a picture.

    The decisions are stored as plain numbers beside the pictures rather than
    inside them, so this column comes back in a tenth of a second where reading
    the frames themselves takes minutes. That is what lets ``to_read`` choose
    which frames are worth reading before any of them is read.
    """
    stored = np.asarray(data.hf_dataset.select_columns("gate")["gate"], dtype=np.float32)
    return stored[:, 0].round().astype(np.int64)


def to_read(kinds: np.ndarray, most: int | None = None, looks: int | None = None) -> np.ndarray:
    """Which frames of a set to read, in the order they were collected.

    ``most`` takes the first few, which is a smoke test. ``looks`` keeps every
    answer that touches a glass and thins the looking ones down to that many,
    which is what makes a set collected from a wider band affordable to read.
    The order is kept because an episode's frames are its table's answers in the
    order the teacher gave them.
    """
    count = len(kinds) if most is None else min(most, len(kinds))
    rows = np.arange(count)
    if looks is None:
        return rows
    looking = rows[kinds[:count] == readings.LOOK]
    if len(looking) <= looks:
        return rows
    kept = np.random.default_rng(0).choice(looking, size=looks, replace=False)
    return np.sort(np.concatenate([rows[kinds[:count] != readings.LOOK], kept]))


def aimed_at(state: np.ndarray) -> tuple[float, float]:
    """Where the glass this answer was aimed at stood, out of the row the policy is shown.

    The decision at the end of that row holds the glass's place, scaled the way
    every place in it is scaled, so this is a reading back rather than a second
    record of the same thing. An answer aimed at no glass gives the middle of the
    table, which subtracts to nothing.
    """
    at = readings.STATE_WIDTH + readings.SELF_WIDTH + len(readings.KINDS)
    across, along = float(state[at]), float(state[at + 1])
    if across == 0.0 and along == 0.0:
        return (0.0, 0.0)
    return (
        TABLE_CENTRE_XY[0] + across * readings.PLACE_SCALE,
        TABLE_CENTRE_XY[1] + along * readings.PLACE_SCALE,
    )


def _picture(frame: dict, shrink: Shrink | None) -> np.ndarray:
    """One frame's picture as the bench's own uint8 RGB, at the size the caller asked for.

    LeRobot hands a picture over as (colour, row, column) floats on 0 to 1, and
    everything either side of this module works in what the camera rendered.
    """
    picture = (frame[CAMERA].numpy().transpose(1, 2, 0) * 255.0).round().astype(np.uint8)
    return picture if shrink is None else shrink(picture)[0]
