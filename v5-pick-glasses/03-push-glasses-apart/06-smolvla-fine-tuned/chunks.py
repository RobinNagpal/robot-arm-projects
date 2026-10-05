"""Turning a push the jaw really made into the chunk the model is trained to emit.

The bench writes down the path the jaw followed on every action, including a
parameterised ``push()``. That recording is the demonstration. It is not yet a
training target, though, and three things have to happen to it first. All
three are arithmetic on the recording; none of them invents a path.

**Cut off the ends the model does not produce.** A recorded push is the jaw
coming down from travel height, feeling forward, pushing, backing off and
lifting clear. ``follow()`` does the coming down and the backing off itself —
it places the jaw above the first waypoint and lifts it after the last — so
what is left for the model is the part in between: the jaw at push height,
travelling forward, up to the far end of the push.

**Resample it to the length of a chunk.** SmolVLA emits a fixed number of
actions in one pass, and that number is a property of the borrowed model, not
a choice made here. A recorded push is longer than that, so the cut path is
resampled to exactly ``CHUNK`` points, evenly along its own length.

That resampling has one consequence worth stating plainly, because it is a
real difference between the student and its teacher. The bench consumes
waypoints a fixed period apart, so **how far apart they are is how fast the
jaw goes**, up to ``TOP_SPEED``, past which the leg simply takes longer.
Squeezing a push into a chunk's worth of waypoints therefore makes the
student's push faster than the teacher's. Over the demonstrations a chunk
covers about 90 mm in 49 waypoint periods, which is about 36 mm/s against the
teacher's 10 mm/s of feeling and 20 mm/s of pushing, and well under the
200 mm/s the jaw tops out at, so the cap never binds on a demonstration.
Nothing can be done about it without either changing the chunk length, which
is the borrowed model's, or asking the model several times per push, which
would spend several pushes of the shared budget on one.

**Read it in the convention both halves of the pair use.** Each waypoint goes
through ``joining.to_state``, which is the same reading, backwards, that
``joining.to_jaw`` applies to what the model emits. So the targets the model
is trained towards are in the units it answers in, and a chunk that came back
unchanged would decode to the push that was recorded.
"""

from __future__ import annotations

import math

import numpy as np
from partners import SLOTS, to_jaw, to_state

from bench import PUSH_HEIGHT, Waypoint

# How many waypoints a chunk holds. This is SmolVLA's own ``chunk_size``, not
# a number chosen here; ``correction.py`` checks the loaded model agrees.
CHUNK = 50

# A waypoint is at push height when it is within this of it. The recording is
# of where the jaw was told to be, so the height is exact to rounding.
AT_PUSH_HEIGHT = 1e-6

# The shortest flat run worth keeping. Below this the jaw barely moved across
# the table and there is no push in the recording to learn from.
LEAST_ACROSS = 0.005

# How far a demonstration may drift when it is read back through the
# convention. The reading clips to the picture's frame, so a push that
# started outside the frame would not survive the round trip, and a target
# the model cannot express is not a target.
FAITHFUL = 0.001


def pushing_part(path: tuple[Waypoint, ...]) -> list[Waypoint]:
    """The stretch of a recorded path the model has to produce: flat, forwards, to the far end.

    Everything above push height is the descent or the lift, which
    ``follow()`` does for itself. Of what is left, the back-off runs
    backwards, so the far end of the push is the waypoint furthest across the
    table from where the jaw came down.
    """
    low = [point for point in path if point.z <= PUSH_HEIGHT + AT_PUSH_HEIGHT]
    if len(low) < 2:
        return []
    start = low[0]
    far = max(range(len(low)), key=lambda i: math.dist((low[i].x, low[i].y), (start.x, start.y)))
    return low[: far + 1]


def across(points: list[Waypoint]) -> float:
    """How far the jaw travels across the table along a path, metres."""
    return sum(
        math.dist((a.x, a.y), (b.x, b.y)) for a, b in zip(points, points[1:], strict=False)
    )


def resampled(points: list[Waypoint], count: int = CHUNK) -> np.ndarray:
    """``count`` waypoints evenly along the path, as an (n, 4) array of x, y, z, heading.

    The first and last points are kept exactly. The heading is interpolated
    through its cosine and sine rather than directly, because a path that
    crosses the back of the circle would otherwise be averaged the long way
    round.
    """
    xy = np.array([[p.x, p.y] for p in points])
    walked = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(xy, axis=0).T))])
    if walked[-1] < LEAST_ACROSS:
        raise ValueError(f"the jaw went {1000 * walked[-1]:.1f} mm across the table; there is no push in it")
    want = np.linspace(0.0, walked[-1], count)
    flat = [np.interp(want, walked, [getattr(p, name) for p in points]) for name in ("x", "y", "z")]
    heading = np.array([p.heading for p in points])
    turned = np.arctan2(np.interp(want, walked, np.sin(heading)), np.interp(want, walked, np.cos(heading)))
    return np.stack([*flat, turned], axis=1)


def as_action(waypoints: np.ndarray) -> np.ndarray:
    """A run of jaw waypoints as the numbers the model emits: (n, 4) in, (n, SLOTS) out."""
    return np.stack([to_state(Waypoint(*row)) for row in waypoints.tolist()])


def drift(waypoints: np.ndarray) -> float:
    """How far a chunk moves when it is read into the convention and back out, metres.

    Zero for anything inside the picture's frame, because the reading is a
    straight scaling there. Large for a push that starts outside it, which is
    a push this model has no way to ask for.
    """
    there_and_back = to_jaw(as_action(waypoints))
    return float(np.max(np.hypot(*(there_and_back[:, :2] - waypoints[:, :2]).T)))


def demonstration(path: tuple[Waypoint, ...]) -> np.ndarray | None:
    """One recorded action as a training target, (CHUNK, SLOTS), or None if there is no push in it.

    Returns None rather than raising, because a recording with nothing to
    learn from is an ordinary thing to meet in a demonstration set and the
    caller counts them.
    """
    part = pushing_part(path)
    if len(part) < 2 or across(part) < LEAST_ACROSS:
        return None
    waypoints = resampled(part)
    if drift(waypoints) > FAITHFUL:
        return None
    action = as_action(waypoints)
    if action.shape != (CHUNK, SLOTS):
        raise AssertionError(f"a chunk is ({CHUNK}, {SLOTS}), not {action.shape}")
    return action
