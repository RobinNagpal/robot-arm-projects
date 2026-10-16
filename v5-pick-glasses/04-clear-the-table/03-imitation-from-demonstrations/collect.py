"""Run the teacher over training tables and write down what it saw and what it did.

The teacher is [solution 2](../02-geometry-ranked), run unchanged through the
bench's own loop. Nothing here invents a path: the teacher answers with the
jaw's waypoints, the bench carries them out, and this records the pair.

**One answer is one demonstration.** That is the difference from problem 3,
where only a push counted. Problem 4 took the overhead camera away, so the
teacher has to drive the arm around before it can act, and four answers in five
are a move to see from somewhere rather than a shove. A policy that was shown
only the shoves would have no idea how to get a look at the table, so the looks
are demonstrations too, and ``collected.json`` says how the set divides.

**What is dropped is the answer that went wrong, and only that one.** A glass
over, a glass shoved out of the zone, a jaw blocked coming down or jammed
against something: a cloned policy copies whatever is in its data, so a path
that ended one of those ways is not one to copy. Every drop is counted by its
reason, because filtering by outcome thins the data exactly on the tables the
teacher found hard, and that thinning is invisible unless it is counted.

**The probe pushes are kept, and problem 3 dropped them.** Problem 3's 5 mm test
push belongs to the shared tipping check and is not a push at the task. Here the
same shove does a second job the camera forced on it: there is no force sensor in
a chunk, so the only way to find out how far away a glass is, is to push a little
and look. That is a real action at the task in problem 4, so it stays, and
``collected.json`` counts the three kinds apart.

**A refused answer is not a demonstration.** The cell's interlock and the bench's
own checks turn some answers away, and the arm never moves, so there is no path
the jaw really followed. Only an answer the bench carried out becomes a frame.

**The teacher was trained somewhere else.** Its ranker is problem 3's fitted file,
loaded and not refitted, and the tables it was fitted on were problem 3's. See
[the set's own README](../demonstrations/README.md).

**The sets go in a folder of their own**, beside this one rather than inside it,
because solution 6 is fitted on the same demonstrations and neither solution
owns them. ``loading.py`` is where their paths are, so this file holds none.

    pixi run python 03-imitation-from-demonstrations/collect.py                 # 300 tables
    pixi run python 03-imitation-from-demonstrations/collect.py --tables 3 --show
    pixi run python 03-imitation-from-demonstrations/collect.py --held-back
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from chunks import ACTION_WIDTH, CHUNK, to_action
from loading import FITTING, HELD_BACK, NAMES, RECORD, REPO
from readings import CAMERA, INSTRUCTION, STATE_WIDTH, to_state

from open_run import clear_table, open_cell
from partners import TEST_SEEDS, TRAVEL_HEIGHT, in_zone
from wrist import WRIST_VIEW_SIZE

HERE = Path(__file__).resolve().parent

# The band the fitting set is drawn from, and the band held back to say how far
# the student is from its teacher on pictures it never saw. Both are below
# TEST_SEEDS, so neither touches the held-out tables.
#
# It starts at a thousand and not at zero for problem 3's reason: the twenty
# tables every solution in this problem is measured on are 0 to 19, and a
# demonstration set that included them would let a student be measured on
# tables it had been fitted on.
FITTING_FIRST, FITTING_TABLES = 1000, 300
HELD_BACK_FIRST, HELD_BACK_TABLES = 8000, 50

# One frame per answer rather than a rate: the model is asked once per answer.
# LeRobot wants a frame rate, so this says what a frame is.
FPS = 1

# Arm seconds for the table while collecting. Far more than the teacher can
# spend, on purpose: the demonstrations are of what it does, not of what a
# budget let it finish. Solution 2's own measurement run uses the same figure.
ROOM_TO_WORK = 100_000.0

# The chunk is stored flat, one row of CHUNK * ACTION_WIDTH numbers, and
# reshaped when it is read back. LeRobot works a dataset's statistics out by
# reducing each feature over an episode's frames, which only comes out the same
# shape on every episode when a frame's feature is one-dimensional.
FEATURES = {
    CAMERA: {"dtype": "image", "shape": (*WRIST_VIEW_SIZE, 3), "names": ["height", "width", "channel"]},
    "observation.state": {"dtype": "float32", "shape": (STATE_WIDTH,), "names": None},
    "action": {"dtype": "float32", "shape": (CHUNK * ACTION_WIDTH,), "names": None},
}

LOOK_KINDS = ("drive", "stay")


def teacher():
    """Solution 2, built as its own measurement run builds it.

    Its folder cannot be imported by name -- the name starts with a digit -- so
    it joins the path here, and only here, which is why this import is inside a
    function.
    """
    folder = HERE.parent / "02-geometry-ranked"
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import ranked

    return ranked.GeometryRanked()


class Watched:
    """Problem 4's cell, with what the model would have been shown kept beside each answer.

    The loop asks the cell for a look, hands the solution that look, and then
    asks the cell to follow whatever came back. So the cell sees both halves of
    a demonstration and nothing else has to be changed to collect one: the
    teacher pushes as it always does and this records around it.
    """

    def __init__(self, inner, teacher) -> None:
        self.inner = inner
        self.teacher = teacher
        self.seen_last: tuple[np.ndarray, tuple, object] | None = None
        self.frames: list[dict] = []

    # ------------------------------------------------- the two interesting calls

    def view(self, jaw):
        picture, seen = self.inner.view(jaw)
        self.seen_last = (picture, seen, jaw)
        return picture, seen

    def follow(self, chunk):
        was_over, was_out = self.inner.toppled(), self._outside()
        record = self.inner.follow(chunk)
        picture, seen, jaw = self.seen_last
        self.frames.append(
            {
                "picture": picture,
                "state": to_state(jaw, seen),
                "path": chunk.waypoints,
                "kind": self._kind(chunk, jaw),
                "why_not": self._why_not(record, was_over, was_out),
            }
        )
        return record

    # ------------------------------------------------------------- the rest of it

    def glasses(self) -> int:
        return self.inner.glasses()

    def truth(self):
        return self.inner.truth()

    def toppled(self) -> int:
        return self.inner.toppled()

    def pickable(self) -> int:
        return self.inner.pickable()

    def charged(self) -> float:
        return self.inner.charged()

    # -------------------------------------------------------------------- judging

    def _outside(self) -> int:
        bench = self.inner.bench
        return sum(1 for i in bench.on_table() if not in_zone(*bench.position(i)))

    def _kind(self, chunk, jaw) -> str:
        """Which of the five kinds of answer this was, for the record.

        Read off the shape of the teacher's own path rather than through
        ``stopping.is_a_push``, and that is deliberate. The stopping rule asks
        whether an answer could touch *a glass*, which depends on how tall the
        glasses on this table are; this asks the simpler question of which of
        the teacher's two kinds of path this is, and the teacher's own answer is
        unambiguous -- a path to go and look is a single waypoint at travel
        height, and a push comes down from there. Tying the label to the
        stopping rule would make it move when that rule is sharpened, and the
        label is only there so a reader can see what the set is made of.

        A push's own kind is read off the teacher, which knows whether it is
        ranging for the glass, testing whether it slides, or pushing it
        somewhere. Nothing scores any of this.
        """
        coming_down = len(chunk.waypoints) > 1 or chunk.waypoints[0].z < TRAVEL_HEIGHT - 1e-9
        if coming_down:
            doing = getattr(self.teacher, "pushed", None)
            return doing.doing if doing is not None else "pushing"
        moved = abs(chunk.waypoints[0].x - jaw.x) > 1e-9 or abs(chunk.waypoints[0].y - jaw.y) > 1e-9
        return "drive" if moved else "stay"

    def _why_not(self, record, was_over: int, was_out: int) -> str | None:
        """Why this answer is not worth copying, or None if it is.

        Read after the table has settled, from the bench's own record of the
        action and from where the glasses are now. Only what this answer changed
        counts: a glass that was already down or already outside the zone was
        some earlier answer's doing and is already on the record as that one's.
        """
        if self.inner.toppled() > was_over:
            return "a glass went over"
        if self._outside() > was_out:
            return "a glass left the glass zone"
        felt = record.felt
        if felt.blocked:
            return "blocked on the way down"
        if felt.jammed:
            return "jammed"
        return None


def demonstrate(seed: int, pick) -> list[dict]:
    """One table cleared by the teacher. Returns the frames it is worth keeping."""
    cell = Watched(open_cell(seed), pick)
    try:
        clear_table(pick, seed, ROOM_TO_WORK, cell=cell)
        return cell.frames
    finally:
        cell.inner.camera.close()


def collect(first: int, count: int, root: Path, show: bool = False) -> dict:
    """Run the teacher over ``count`` tables and write what it did into a dataset at ``root``."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    if first + count > TEST_SEEDS:
        raise ValueError(f"tables {TEST_SEEDS} and up are the held-out ones; nothing may be fitted on them")
    shutil.rmtree(root, ignore_errors=True)
    data = LeRobotDataset.create(repo_id=REPO, fps=FPS, root=root, features=FEATURES, use_videos=False)

    pick = teacher()
    dropped: Counter = Counter()
    kinds: Counter = Counter()
    lengths: list[int] = []
    kept = 0
    started = time.time()
    for seed in range(first, first + count):
        frames = demonstrate(seed, pick)
        written = 0
        for frame in frames:
            kinds[frame["kind"]] += 1
            if frame["why_not"] is not None:
                dropped[frame["why_not"]] += 1
                continue
            action = to_action(frame["path"])
            if action is None:
                dropped[f"a path of more than {CHUNK} waypoints"] += 1
                continue
            lengths.append(len(frame["path"]))
            data.add_frame(
                {
                    CAMERA: frame["picture"],
                    "observation.state": frame["state"],
                    "action": action.reshape(-1),
                    "task": INSTRUCTION,
                }
            )
            written += 1
        if written:
            data.save_episode()
            kept += written
        if show or (seed - first + 1) % 25 == 0:
            print(
                f"  table {seed}: {written} kept of {len(frames)}, {kept} so far, "
                f"{time.time() - started:.0f}s",
                flush=True,
            )
    data.finalize()

    spent = time.time() - started
    looks = sum(kinds[kind] for kind in LOOK_KINDS)
    summary = {
        "teacher": "02-geometry-ranked, with problem 3's ranker, which was fitted on problem 3's tables",
        "band": {"first_table": first, "tables": count, "held_out_from": TEST_SEEDS},
        "demonstrations": kept,
        "answers": sum(kinds.values()),
        "answers_a_table": round(sum(kinds.values()) / count, 1),
        "kinds": dict(kinds.most_common()),
        "looking_share": round(looks / sum(kinds.values()), 3) if kinds else 0.0,
        "dropped": dict(dropped.most_common()),
        "chunk": CHUNK,
        "action_width": ACTION_WIDTH,
        "state_width": STATE_WIDTH,
        "picture": list(WRIST_VIEW_SIZE),
        "waypoints_a_path": _band(lengths),
        "seconds": round(spent, 1),
        "seconds_a_table": round(spent / count, 2),
        "seconds_a_demonstration": round(spent / kept, 3) if kept else None,
    }
    _remember(root, summary)
    return summary


def _remember(root: Path, summary: dict) -> None:
    """Add this set to the record beside the sets, leaving the other set alone.

    One file for both, because everything inside a set is rendered pictures and
    is left out of git, while this is what the collection measured and belongs
    in it. The two sets are usually collected in separate runs, so a run reads
    the record back rather than writing over it.
    """
    record = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    record[NAMES[root]] = summary
    RECORD.write_text(json.dumps(record, indent=2) + "\n")


def _band(lengths: list[int]) -> dict:
    """The shape of the paths kept: a chunk has to hold the longest of them."""
    if not lengths:
        return {}
    sorted_lengths = sorted(lengths)
    return {
        "least": sorted_lengths[0],
        "median": sorted_lengths[len(sorted_lengths) // 2],
        "90th": sorted_lengths[int(0.9 * (len(sorted_lengths) - 1))],
        "most": sorted_lengths[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--held-back", action="store_true", help="the set held back from fitting, not the fitting one"
    )
    parser.add_argument("--tables", type=int, default=None)
    parser.add_argument("--first", type=int, default=None)
    parser.add_argument("--show", action="store_true", help="print every table")
    arguments = parser.parse_args()

    root = HELD_BACK if arguments.held_back else FITTING
    first, tables = (
        (HELD_BACK_FIRST, HELD_BACK_TABLES) if arguments.held_back else (FITTING_FIRST, FITTING_TABLES)
    )
    if arguments.first is not None:
        first = arguments.first
    if arguments.tables is not None:
        tables = arguments.tables

    summary = collect(first, tables, root, arguments.show)
    print(
        f"\n{summary['demonstrations']} demonstrations from {tables} tables "
        f"({summary['answers_a_table']} answers a table) in {summary['seconds']:.0f}s"
    )
    print(f"kinds    {summary['kinds']}, {100 * summary['looking_share']:.0f}% of them looking")
    print(f"dropped  {summary['dropped'] or 'nothing'}")
    print(f"paths    {summary['waypoints_a_path']} waypoints, into a chunk of {CHUNK}")
    print(f"\nthe set is in {root}, and what it is in {RECORD}")


if __name__ == "__main__":
    main()
