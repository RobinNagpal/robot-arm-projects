"""One collected demonstration, read as something the borrowed model can be fitted towards.

This is the only new thinking in the fitting half of this folder. Everything
else about the fit is problem 3's, imported through ``borrowed.py``, because the
two problems are meant to be compared. What cannot be imported is the step from
problem 4's demonstrations to the borrowed model's convention, and this module
is that step.

**What a demonstration holds.** The collector wrote the picture from the camera
on the arm, the readings of the glasses it caught beside where the jaw was
standing, and the path the jaw then followed. The path is stored padded out to
two hundred rows, with a column saying how many of them are the path.

**What the model takes.** Six numbers of somebody else's arm for the state, a
picture, one sentence, and fifty rows of six numbers for the answer. The join
between those six numbers and this cell's jaw is problem 3's ``joining.py``,
held still, so a target written here is in the units the model answers in and a
chunk that came back unchanged would decode to the path that was recorded.

Three things happen on the way, and none of them invents a path.

**The declarations are dropped, and the glasses are dropped from the state.**
Problem 4's demonstrations hold the teacher's own "this table needs nothing
more", which has no path in it at all; `Targets` leaves those frames out,
because a model that answers with a path has nothing to be fitted towards on
them. Solution 3's gate is the model those frames are for.

The model's state is six numbers and
they are joint readings, so the only thing in a ``Look`` that fits is where the
jaw is standing. The glasses it caught are in the picture, which is what the
model is expected to read them from. Problem 4's own students take the readings
as numbers beside the picture; this one cannot, and that is a property of the
borrowed model rather than a choice made here.

**The descent is dropped from the path.** Every demonstrated push starts at
travel height and comes straight down over its first twenty-three waypoints
before it drives anywhere. ``follow()`` does that drop itself -- it places the
jaw above the first waypoint and lowers it on -- so a chunk that asked for it
would be asking for the drop twice. What is left is the flat part, which is what
the model has to produce. Problem 3's solution 6 cuts a push down the same way
and its ``pushing_part`` is what does it here.

**The path is padded, and squeezed only when it will not fit.** A chunk is fifty
rows and most paths are shorter, so the path keeps the teacher's own spacing and
the last pose is repeated to the end. That matters because the bench eats
waypoints at a fixed rate, so how far apart they are *is* how fast the jaw goes:
a padded path pushes at the teacher's speed, and a resampled one does not.
Problem 4's own chunk convention pads for exactly this reason. Measured over the
fitting set, 1,824 of the 2,051 pushes fit in fifty rows -- 89 per cent -- and
the 227 that do not are resampled into them, which asks for the teacher's own
path at a median of 1.6 times its speed and 3.3 times at the worst. That is the
one place a target is not the teacher's own motion, and ``Counts`` keeps the
number so it can be reported rather than assumed.

**A look is the same shape held still.** Four answers in five are the teacher
driving the arm somewhere it can see from, which is one waypoint at travel
height. There is no "still going" column among the model's six slots -- adding
one would change ``joining.py``, and holding that still is what keeps this
solution comparable with solution 5 -- so a look is written as its pose repeated
for the whole chunk. The bench skips a leg of no length, so such a chunk costs
the crossing and nothing else, which is what the teacher's look costs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from borrowed import MODEL_CHUNK, chunks, joining, loading, policy, pushing_chunks, readings

from partners import Waypoint

# What one demonstration became. ``looking`` and ``pushing`` are the teacher's
# own answers kept at its own spacing; ``squeezed`` is a push too long for the
# chunk, resampled into it.
LOOKING, PUSHING, SQUEEZED = "looking", "pushing", "squeezed"


@dataclass
class Counts:
    """What the reading did to a set of demonstrations, for the fit's own record.

    Diagnosis rather than score. The one number that matters to a reader is
    ``squeezed``: those are the demonstrations the student is asked to push
    faster than its teacher did.
    """

    kinds: Counter = field(default_factory=Counter)
    pulled_in: int = 0

    def saw(self, kind: str, pulled: int) -> None:
        self.kinds[kind] += 1
        self.pulled_in += pulled

    def summary(self) -> dict:
        read = sum(self.kinds.values())
        return {
            "demonstrations_read": read,
            "kinds": dict(self.kinds),
            "squeezed_share": round(self.kinds[SQUEEZED] / read, 4) if read else 0.0,
            "waypoints_pulled_inside_the_limits": self.pulled_in,
        }


def jaw_from(state: np.ndarray) -> Waypoint:
    """Where the jaw was standing, out of a stored observation.

    The first five numbers of the row are the jaw, and this undoes what
    ``readings.to_state`` did to them: the flat position is measured from the
    middle of the table and everything is divided by ``readings.PLACE_SCALE``,
    which is a unit for putting metres near one rather than any measurement. The
    heading is carried as a cosine and a sine, because an angle wraps at pi.

    The stored row is longer than the table's own numbers, because solution 3's
    gate and policy are fitted on the same demonstrations and the row carries
    what they need as well. This model reads the jaw and nothing else, so what
    the row holds after the table is no concern of this function's; what it must
    not do is assume a length, which is what it used to do and what stopped a
    fit the first time the row grew.
    """
    row = np.asarray(state, dtype=float)
    if row.ndim != 1 or len(row) < readings.STATE_WIDTH:
        raise ValueError(
            f"a stored observation holds the table's {readings.STATE_WIDTH} numbers "
            f"before anything else, and this one is {row.shape}"
        )
    return Waypoint(
        x=row[0] * readings.PLACE_SCALE + readings.TABLE_CENTRE_XY[0],
        y=row[1] * readings.PLACE_SCALE + readings.TABLE_CENTRE_XY[1],
        z=row[2] * readings.PLACE_SCALE,
        heading=float(np.arctan2(row[4], row[3])),
    )


def path_of(action: np.ndarray) -> tuple[tuple[Waypoint, ...], int]:
    """The path the jaw really followed, out of a stored action.

    Problem 4's own ``chunks.to_waypoints`` is what reads it: it takes the rows
    the sixth column claims and pulls each waypoint inside the jaw's limits.
    Nothing in a demonstration should need pulling in, because the bench carried
    it out, and the count comes back so that an assumption is a measurement.
    """
    return chunks.to_waypoints(action)


def as_target(path: tuple[Waypoint, ...], chunk: int = MODEL_CHUNK) -> tuple[np.ndarray, str]:
    """One followed path as the ``(chunk, SLOTS)`` target the model is fitted towards.

    Returns the target and which of the three kinds of answer it was. It raises
    rather than returning nothing when a path cannot be written in the model's
    convention, because the measurement says there are none: every jaw pose in
    the fitting set is inside the frame the convention maps onto, so the round
    trip is exact. A target the model cannot express is not a target, and a fit
    that met one should stop rather than learn something the model cannot say.
    """
    if not path:
        raise ValueError("a followed path has at least one waypoint")
    flat = pushing_chunks.pushing_part(tuple(path))
    if len(flat) < 2 or pushing_chunks.across(flat) < pushing_chunks.LEAST_ACROSS:
        kind = LOOKING
        rows = np.repeat(_as_rows(path[-1:]), chunk, axis=0)
    elif len(flat) <= chunk:
        kind = PUSHING
        rows = _as_rows(flat)
        # The last pose, held. The target after the push has ended is "stand
        # still", which is a leg of no length and costs the arm nothing.
        rows = np.concatenate([rows, np.repeat(rows[-1:], chunk - len(rows), axis=0)])
    else:
        kind = SQUEEZED
        rows = pushing_chunks.resampled(flat, chunk)

    if (wrong := pushing_chunks.drift(rows)) > pushing_chunks.FAITHFUL:
        raise ValueError(
            f"this path moves {1000 * wrong:.1f} mm when it is read into the model's convention "
            "and back out, so the model cannot express it; the fitting set was measured to hold none"
        )
    return pushing_chunks.as_action(rows), kind


def _as_rows(path) -> np.ndarray:
    """A run of waypoints as the ``(n, 4)`` array the borrowed reading takes."""
    return np.asarray([[point.x, point.y, point.z, point.heading] for point in path], dtype=float)


class Targets:
    """One collected set of demonstrations, as the borrowed model wants to be shown it.

    A thin wrapper around the set rather than a second copy of it: every frame
    comes out of ``loading``'s own dataset, and what this adds is the three
    conversions above and the model's own names for the four things it takes.
    Problem 3's fitting recipe can then pre-process a batch and measure a
    distance without knowing anything about problem 4.

    **The set is streamed and not read into memory**, which is the one place
    this does not use ``loading.load``. That function hands back every frame as
    one array, which is what a small model fitted from nothing wants: it reads
    its pictures shrunk, so the whole set is a few hundred megabytes. This model
    reads the picture at the size the camera rendered it, and eleven thousand of
    those is close to five gigabytes, on a machine that is also holding the
    model. So the frames arrive one at a time, as problem 3's own fit takes
    them.
    """

    def __init__(self, root: Path, counts: Counts | None = None) -> None:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        if not (root / "meta").exists():
            raise FileNotFoundError(
                f"no demonstrations at {root}. Collect them with "
                "`pixi run python -u 03-imitation-from-demonstrations/collect.py`."
            )
        self.data = LeRobotDataset(repo_id=loading.REPO, root=root)
        self.counts = Counts() if counts is None else counts
        # The teacher's own "this table needs nothing more" is in the set, and it
        # is not a path: there is nothing for this model to be fitted towards on
        # such a frame. Solution 3's gate is what those frames are for. They are
        # left out here by index rather than by copying the set, which is the one
        # thing this class exists not to do.
        self.frames = [i for i in range(len(self.data)) if not self._is_a_declaration(i)]

    def _is_a_declaration(self, i: int) -> bool:
        """Whether this frame is the teacher saying the table is finished."""
        return int(round(float(self.data[i]["gate"][0].item()))) == readings.DONE

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def tables(self) -> int:
        """How many tables the set was collected from. One episode is one table."""
        return self.data.num_episodes

    def __getitem__(self, i: int) -> dict:
        frame = self.data[self.frames[i]]
        path, pulled = path_of(frame["action"].numpy().reshape(chunks.CHUNK, chunks.ACTION_WIDTH))
        target, kind = as_target(path)
        self.counts.saw(kind, pulled)
        state = joining.to_state(jaw_from(frame["observation.state"]))
        return {
            # The wrist picture goes into the one camera slot the model declares
            # that this cell fills. That is solution 5's join, unchanged: the
            # model has three camera slots and no notion of where any of them is.
            policy.CAMERA: frame[readings.CAMERA],
            "observation.state": torch.from_numpy(state).float(),
            "action": torch.from_numpy(target).float(),
            # Solution 5's sentence and not problem 4's own, because the pair is
            # only clean while everything but the weights is held still.
            "task": joining.INSTRUCTION,
        }


class Spread:
    """A handful of demonstrations from across a set, as a set in its own right.

    Problem 3's ``chunk_error_mm`` measures the first few frames of whatever it
    is handed. The first few frames of a collected set are its first table, and
    one table is not a sample of fifty, so this stands in front of a set and
    hands over chosen frames instead. It is also how the distance is reported
    for looks and for pushes apart, which matters here because four answers in
    five are looks and a median over the mixture would be a median over those.
    """

    def __init__(self, sets: Targets, which: list[int]) -> None:
        self.sets = sets
        self.which = list(which)

    def __len__(self) -> int:
        return len(self.which)

    def __getitem__(self, i: int) -> dict:
        return self.sets[self.which[i]]


def evenly(count: int, over: int) -> list[int]:
    """``count`` indices spread evenly over ``over`` of them, or all of them if there are fewer."""
    if over <= count:
        return list(range(over))
    return [int(round(i)) for i in np.linspace(0, over - 1, count)]


def by_kind(sets: Targets) -> dict[str, list[int]]:
    """Which frames of a set are looks and which are pushes.

    Read out of the stored action rather than assumed, because what a
    demonstration is was decided by the teacher. It costs one pass over the set
    and is worth it: the two kinds are measured apart.

    The rows are read through the set's own list of frames, because a set
    leaves the teacher's declarations out and they are still in the dataset
    underneath. Reading the dataset at the set's own numbering walks off the
    end of the frames it kept and eventually lands on a declaration, which has
    no path at all, and the fit then stops on a path it cannot express.
    """
    found: dict[str, list[int]] = {LOOKING: [], PUSHING: [], SQUEEZED: []}
    for i in range(len(sets)):
        row = sets.data[sets.frames[i]]
        action = row["action"].numpy().reshape(chunks.CHUNK, chunks.ACTION_WIDTH)
        path, _ = path_of(action)
        found[as_target(path)[1]].append(i)
    return found
