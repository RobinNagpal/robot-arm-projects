"""Run the teacher, watch what the jaw did, and write it down as a LeRobot dataset.

The teacher is [solution 2](../02-geometry-ranked), run unchanged over the
training tables. Every push it makes is a finished example, and nobody holds a
controller: the tables are drawn from numbers and the chooser is a program, so
the data costs simulator time and nothing else.

**A demonstration is a picture and a path.** The picture is what the model
would have been shown at that moment — the straight-down view, taken just
before the jaw moves — together with where the jaw was standing and the one
instruction. The path is what the jaw really did, which the bench writes into
``Record.waypoints`` on every action, cut and resampled by ``chunks.py``.
Nothing here invents a trajectory; the teacher thinks in push parameters and
the bench's own macro turns them into the motion that is recorded.

**The pushes that went wrong are dropped**, which is the right thing to do and
has a cost the document is explicit about: what is dropped is exactly the set
of situations the teacher handled badly, so the policy is fitted on the easy
half of its teacher's own experience. The counts below say how much was
dropped and why, so the size of that bias is on the record rather than
guessed at.

The 5 mm test pushes are dropped too, and for a different reason. A probe
belongs to the shared tipping check in [pushing without
toppling](../../docs/03-push-glasses-apart/pushing-without-toppling.md), not
to the chooser, and both halves of the pair make it the same way through
``push()``. It is not a push at the task and it is not this model's to learn.

    pixi run python 06-smolvla-fine-tuned/demonstrations.py                 # 400 training tables
    pixi run python 06-smolvla-fine-tuned/demonstrations.py --tables 20
    pixi run python 06-smolvla-fine-tuned/demonstrations.py --check         # the tuning tables
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from collections import Counter
from pathlib import Path

import numpy as np
from chunks import CHUNK, across, demonstration, pushing_part
from partners import CAMERA, INSTRUCTION, SLOTS, jaw_now, taught, teacher, to_state

from bench import STANDING_TILT_DEG, TEST_SEEDS, Bench, Push, Waypoint, in_zone
from top_view import TOP_VIEW_SIZE, TopCamera

HERE = Path(__file__).parent
FITTING = HERE / "demonstrations"
TUNING = HERE / "demonstrations-check"
REPO = "local/push-glasses-apart"

# Tables the teacher is run over to make the fitting set, and the tables it is
# run over to make the set that says when to stop. Both are below TEST_SEEDS,
# so neither overlaps the held-out tables the scorecard is read from. The
# tuning tables are solution 4's, for the same reason it uses them.
FITTING_FIRST, FITTING_TABLES = 0, 400
TUNING_FIRST, TUNING_TABLES = 9500, 50

# One frame per decision rather than a rate: the model is asked once per push.
# LeRobot wants a frame rate, so this says what a frame is.
FPS = 1

# The chunk is stored flat, one row of CHUNK * SLOTS numbers, and reshaped
# when it is read back. LeRobot computes a dataset's statistics by reducing
# each feature over the frames of an episode, which only comes out the same
# shape on every episode when a frame's feature is one-dimensional. So a
# (CHUNK, SLOTS) action is not something its statistics survive, and this is
# the shape that is.
FEATURES = {
    CAMERA: {"dtype": "image", "shape": (*TOP_VIEW_SIZE, 3), "names": ["height", "width", "channel"]},
    "observation.state": {"dtype": "float32", "shape": (SLOTS,), "names": None},
    "action": {"dtype": "float32", "shape": (CHUNK * SLOTS,), "names": None},
}


class Watched(Bench):
    """A bench that also takes the picture the model would have been shown.

    The teacher's loop decides from ``look()`` and then calls ``push()``, so
    there is no moment between the two for a caller to render at. Taking the
    picture inside ``push()`` puts it exactly there: the table as it stood
    when the push was chosen, before the jaw moved.
    """

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.camera = TopCamera(self)
        self.before: tuple[np.ndarray, Waypoint] | None = None

    def push(self, push: Push):
        self.before = (self.camera.view(), jaw_now(self))
        return super().push(push)

    def close(self) -> None:
        self.camera.close()


def went_well(table: Bench) -> str | None:
    """Why the push that has just been made is not worth imitating, or None if it is.

    Read after the table has settled, from the bench's own record of the
    action and from where the glasses are now.
    """
    felt = table.records[-1].felt
    if felt.blocked:
        return "blocked on the way down"
    if felt.touched is None:
        return "never touched anything"
    if felt.jammed:
        return "jammed"
    for glass in table.on_table():
        if table.tilt(glass) >= STANDING_TILT_DEG:
            return "a glass went over"
        if not in_zone(*table.position(glass)):
            return "a glass left the zone"
    return None


def collect(first: int, tables: int, root: Path, show: bool = False) -> dict:
    """Run the teacher over ``tables`` tables and write what it did into a dataset at ``root``."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    if first + tables > TEST_SEEDS:
        raise ValueError(f"tables {TEST_SEEDS} and up are the held-out ones; nothing may be fitted on them")
    shutil.rmtree(root, ignore_errors=True)
    data = LeRobotDataset.create(repo_id=REPO, fps=FPS, root=root, features=FEATURES, use_videos=False)

    pick = teacher()
    dropped: Counter = Counter()
    kept, shapes = 0, {"across_mm": [], "step_mm": []}
    started = time.time()
    for seed in range(first, first + tables):
        table = Watched(seed)
        frames = []

        def watch(seen, push, felt, probe, table=table, frames=frames):
            if probe:
                dropped["a 5 mm test push"] += 1
                return
            why = went_well(table)
            if why is not None:
                dropped[why] += 1
                return
            action = demonstration(table.records[-1].waypoints)
            if action is None:
                dropped["no push in the recording"] += 1
                return
            picture, jaw = table.before
            frames.append((picture, jaw, action, table.records[-1].waypoints))

        taught(table, pick, watch=watch)
        for picture, jaw, action, path in frames:
            data.add_frame(
                {
                    CAMERA: picture,
                    "observation.state": to_state(jaw).astype(np.float32),
                    "action": action.astype(np.float32).reshape(-1),
                    "task": INSTRUCTION,
                }
            )
            part = pushing_part(path)
            shapes["across_mm"].append(1000 * across(part))
            shapes["step_mm"].append(1000 * across(part) / (CHUNK - 1))
        if frames:
            data.save_episode()
            kept += len(frames)
        table.close()
        if show or (seed - first + 1) % 50 == 0:
            print(f"  table {seed}: {len(frames)} kept, {kept} so far, {time.time() - started:.0f}s")
    data.finalize()

    summary = {
        "tables": tables,
        "first_table": first,
        "demonstrations": kept,
        "dropped": dict(dropped),
        "chunk": CHUNK,
        "across_mm_median": round(float(np.median(shapes["across_mm"])), 1) if kept else None,
        "step_mm_median": round(float(np.median(shapes["step_mm"])), 1) if kept else None,
        "seconds": round(time.time() - started, 1),
    }
    (root / "collected.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="the tuning tables, not the fitting ones")
    parser.add_argument("--tables", type=int, default=None)
    parser.add_argument("--first", type=int, default=None)
    parser.add_argument("--show", action="store_true", help="print every table")
    arguments = parser.parse_args()

    root = TUNING if arguments.check else FITTING
    first = arguments.first if arguments.first is not None else (TUNING_FIRST if arguments.check else 0)
    tables = arguments.tables or (TUNING_TABLES if arguments.check else FITTING_TABLES)

    summary = collect(first, tables, root, arguments.show)
    print(f"\n{summary['demonstrations']} demonstrations from {tables} tables in {summary['seconds']:.0f}s")
    print(f"dropped  {summary['dropped'] or 'nothing'}")
    print(
        f"chunks   {summary['across_mm_median']} mm across the table, "
        f"{summary['step_mm_median']} mm a waypoint"
    )
    print(f"\nsaved to {root}")


if __name__ == "__main__":
    main()
