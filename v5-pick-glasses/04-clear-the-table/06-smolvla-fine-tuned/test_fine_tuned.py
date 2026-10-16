"""Tests for the fitted model's two halves, with no model, no weights and no physics.

Nothing here loads a checkpoint or a correction. A test that needs two gigabytes
off the internet is not a test, and what is worth testing is not the weights --
they are made by the fitting and they change with its seed -- but the two joins
either side of them.

**The first join is the demonstrations.** A stored demonstration has to arrive at
the model as something it could have said itself, and the test of that is a round
trip: read a path into the model's convention, decode it back, and ask whether
the jaw would go where the teacher's jaw went. That is checked over families of
paths rather than over one path, because the three kinds of answer the teacher
gives -- a look, a push that fits in a chunk and a push that does not -- are read
by three different arms of the same function.

**The second join is the conversation.** The solution has to say when a table is
finished, and it says it by going quiet. The tests drive that rule from both
sides over a family of spell lengths: a quiet spell one answer short of the line
is not a declaration, and a push in the middle of a spell starts the count again.

The model is a stand-in that answers with the paths the test chooses, and the
cell is the one the loop's own tests use: no renderer, no graphics context and no
physics.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
import targets
import weights
from borrowed import MODEL_CHUNK, chunks, joining, readings
from fine_tuned import FineTuned
from targets import LOOKING, PUSHING, SQUEEZED

from contract import Look
from open_run import HOME, clear_table
from partners import JAW_HALF_HEIGHT, PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Felt, Record, Seen, Waypoint

# A picture of the shape the policy takes, which nothing in these tests reads.
PICTURE = np.zeros((384, 384, 3), dtype=np.uint8)
# Where the glasses stand on these tables, which is the middle of the frame the
# model's output maps onto. Nothing here depends on the figure.
MIDDLE = (0.48, -0.26)


def glass(i: int = 0, x: float = 0.48, y: float = -0.26, height: float = 0.14) -> Seen:
    """One reading of one glass, of a size nothing here depends on."""
    return Seen(id=i, x=x, y=y, height=height, widest=0.07, foot=0.055, standing=True)


def look_path(draw: random.Random) -> tuple[Waypoint, ...]:
    """One drawn demonstration of the teacher going to stand somewhere, which is one waypoint."""
    return (
        Waypoint(
            x=MIDDLE[0] + draw.uniform(-0.15, 0.15),
            y=MIDDLE[1] + draw.uniform(-0.15, 0.15),
            z=TRAVEL_HEIGHT,
            heading=draw.uniform(-math.pi, math.pi),
        ),
    )


def push_path(draw: random.Random, waypoints: int) -> tuple[Waypoint, ...]:
    """One drawn demonstration of a push: the drop, and then the flat drive.

    The shape is the teacher's own, read off the collected set: twenty-three
    waypoints coming straight down from travel height, then a millimetre of
    table at a time at the height the jaw pushes at.
    """
    start = (MIDDLE[0] + draw.uniform(-0.1, 0.1), MIDDLE[1] + draw.uniform(-0.1, 0.1))
    heading = draw.uniform(-math.pi, math.pi)
    drop = [
        Waypoint(start[0], start[1], TRAVEL_HEIGHT - (TRAVEL_HEIGHT - PUSH_HEIGHT) * i / 22, heading)
        for i in range(23)
    ]
    flat = [
        Waypoint(
            start[0] + 0.001 * i * math.cos(heading),
            start[1] + 0.001 * i * math.sin(heading),
            PUSH_HEIGHT,
            heading,
        )
        for i in range(waypoints)
    ]
    return tuple(drop + flat)


def stored(path: tuple[Waypoint, ...]) -> np.ndarray:
    """One path as the collector stores it: problem 4's own padded two hundred rows."""
    action = chunks.to_action(path)
    assert action is not None, "the drawn path should fit in problem 4's own chunk"
    return action


def flat_part(path: tuple[Waypoint, ...]) -> list[Waypoint]:
    """The waypoints of a path that are down at the height the jaw pushes at."""
    return [point for point in path if point.z <= PUSH_HEIGHT + 1e-6]


class Stub:
    """A stand-in for the fitted model: answers with the paths it is handed.

    The last answer repeats for ever, so a test need only write the part of the
    conversation it is about.
    """

    def __init__(self, paths) -> None:
        self.paths = list(paths)
        self.asked: list[Waypoint] = []
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1

    def ask(self, picture: np.ndarray, jaw: Waypoint) -> np.ndarray:
        self.asked.append(jaw)
        return self.paths[min(len(self.asked) - 1, len(self.paths) - 1)]


class Cell:
    """The work cell with nothing in it, answering ``open_run.Cell`` and no more.

    Written again here rather than imported from the bench's own test file: a
    test file is not a module other folders import, and importing one would make
    this folder's tests fail the day the bench's tests were rearranged.
    """

    def __init__(self, seen=(), toppled: int = 0, pickable: int = 0) -> None:
        self.seen = tuple(seen)
        self.fell = toppled
        self.room = pickable
        self.followed: list[Chunk] = []

    def glasses(self) -> int:
        return max(1, len(self.seen))

    def view(self, jaw: Waypoint):
        return PICTURE, self.seen

    def truth(self):
        return self.seen

    def follow(self, chunk: Chunk) -> Record:
        self.followed.append(chunk)
        felt = Felt(blocked=False, touched=None, jammed=False, peak=0.0, pushed=0.0)
        return Record(push=chunk.as_push(), felt=felt, landed=chunk.aim, waypoints=chunk.waypoints)

    def toppled(self) -> int:
        return self.fell

    def pickable(self) -> int:
        return self.room

    def charged(self) -> float:
        return 0.0


def flat_chunk(z: float, points: int = MODEL_CHUNK, across: float = 0.1) -> np.ndarray:
    """A drawn answer at one height, crossing ``across`` metres of table. (n, 4) waypoints."""
    return np.stack(
        [
            np.linspace(MIDDLE[0] - across / 2, MIDDLE[0] + across / 2, points),
            np.full(points, MIDDLE[1]),
            np.full(points, z),
            np.zeros(points),
        ],
        axis=1,
    )


# --------------------------------------------------------------- the demonstrations


def test_a_look_is_read_as_one_pose_held_for_the_whole_chunk():
    draw = random.Random(1)
    for _ in range(40):
        path = look_path(draw)
        target, kind = targets.as_target(targets.path_of(stored(path))[0])
        assert kind == LOOKING
        assert target.shape == (MODEL_CHUNK, joining.SLOTS)
        back = joining.to_jaw(target)
        # Every row is the pose the teacher drove to, so the jaw is being asked
        # to stand there and do nothing, which is what a look costs.
        assert np.allclose(back[:, :3], back[0, :3])
        # To a micrometre, which is below anything the arm can do and above
        # the resolution of the float32 a demonstration is stored in.
        assert back[0, 0] == pytest.approx(path[0].x, abs=1e-6)
        assert back[0, 1] == pytest.approx(path[0].y, abs=1e-6)
        assert back[0, 2] == pytest.approx(path[0].z, abs=1e-6)


def test_a_push_that_fits_keeps_the_teachers_own_waypoints():
    draw = random.Random(2)
    # From eight waypoints up, because a flat run of under five millimetres has
    # no push in it and is read as the jaw being asked to stand still instead.
    # Up to one short of a chunk, because the last waypoint of the drop is
    # already at the pushing height and counts as part of the flat run.
    for waypoints in range(8, MODEL_CHUNK, 7):
        path = push_path(draw, waypoints)
        target, kind = targets.as_target(targets.path_of(stored(path))[0])
        assert kind == PUSHING
        back = joining.to_jaw(target)
        wanted = flat_part(path)
        # The teacher's flat waypoints, at the teacher's own spacing, so the
        # student pushes at the teacher's speed and not faster.
        for i, point in enumerate(wanted):
            assert back[i, 0] == pytest.approx(point.x, abs=1e-6)
            assert back[i, 1] == pytest.approx(point.y, abs=1e-6)
            assert back[i, 2] == pytest.approx(PUSH_HEIGHT, abs=1e-6)
        # And then the end of the push, held, which costs the arm nothing.
        assert np.allclose(back[len(wanted) :, :3], back[len(wanted) - 1, :3], atol=1e-6)


def test_the_descent_is_left_to_the_cell():
    """A target starts down at the pushing height: ``follow()`` does the drop itself."""
    draw = random.Random(3)
    for _ in range(20):
        path = push_path(draw, draw.randint(8, 40))
        target, _ = targets.as_target(targets.path_of(stored(path))[0])
        assert joining.to_jaw(target)[0, 2] == pytest.approx(PUSH_HEIGHT, abs=1e-6)


def test_a_push_too_long_for_the_chunk_is_squeezed_into_it():
    draw = random.Random(4)
    for waypoints in (MODEL_CHUNK + 1, 90, 167):
        path = push_path(draw, waypoints)
        target, kind = targets.as_target(targets.path_of(stored(path))[0])
        assert kind == SQUEEZED
        back = joining.to_jaw(target)
        wanted = flat_part(path)
        # The same path from the same place to the same place, in fewer
        # waypoints, which is the jaw asked to travel it faster.
        assert back[0, 0] == pytest.approx(wanted[0].x, abs=1e-6)
        assert back[-1, 0] == pytest.approx(wanted[-1].x, abs=1e-6)
        assert back[-1, 1] == pytest.approx(wanted[-1].y, abs=1e-6)
        steps = np.hypot(*np.diff(back[:, :2], axis=0).T)
        assert np.median(steps) > 0.001, "a squeezed push asks for a longer step than the teacher's"


def test_a_path_the_model_cannot_express_stops_the_fit():
    """A push out at the table's edge is outside the frame the convention maps onto."""
    far = tuple(Waypoint(x=1.1, y=0.6 - 0.001 * i, z=PUSH_HEIGHT, heading=0.0) for i in range(30))
    with pytest.raises(ValueError, match="cannot express"):
        targets.as_target(far)


def test_the_jaw_pose_is_recovered_from_a_stored_observation():
    draw = random.Random(5)
    for _ in range(40):
        jaw = Waypoint(
            x=MIDDLE[0] + draw.uniform(-0.2, 0.2),
            y=MIDDLE[1] + draw.uniform(-0.2, 0.2),
            z=draw.uniform(PUSH_HEIGHT, TRAVEL_HEIGHT),
            heading=draw.uniform(-math.pi, math.pi),
        )
        seen = [glass(i, x=0.4 + 0.05 * i, y=-0.3) for i in range(draw.randint(0, 3))]
        back = targets.jaw_from(readings.to_state(jaw, seen))
        assert back.x == pytest.approx(jaw.x, abs=1e-5)
        assert back.y == pytest.approx(jaw.y, abs=1e-5)
        assert back.z == pytest.approx(jaw.z, abs=1e-5)
        assert math.cos(back.heading) == pytest.approx(math.cos(jaw.heading), abs=1e-5)
        assert math.sin(back.heading) == pytest.approx(math.sin(jaw.heading), abs=1e-5)


def test_what_the_reading_did_is_counted_by_kind():
    counts = targets.Counts()
    counts.saw(LOOKING, 0)
    counts.saw(PUSHING, 0)
    counts.saw(SQUEEZED, 2)
    summary = counts.summary()
    assert summary["demonstrations_read"] == 3
    assert summary["kinds"] == {LOOKING: 1, PUSHING: 1, SQUEEZED: 1}
    assert summary["squeezed_share"] == pytest.approx(1 / 3, abs=1e-3)
    assert summary["waypoints_pulled_inside_the_limits"] == 2


def test_a_sample_is_spread_across_a_set_rather_than_taken_from_its_front():
    assert targets.evenly(4, 100) == [0, 33, 66, 99]
    assert targets.evenly(10, 3) == [0, 1, 2]


# --------------------------------------------------------------- the conversation


def answers(solution: FineTuned, cell: Cell, seconds: float = 120.0):
    """Walk one table with this solution and hand back how it ended."""
    return clear_table(solution, seed=0, seconds_left=seconds, cell=cell)


def test_it_says_done_after_a_quiet_spell_and_not_before():
    """The spell has to be as long as the solution's own count, whatever that count is."""
    for quiet_for in (3, 8, 16):
        # High enough that the hand clears the glass on the table.
        quiet = flat_chunk(TRAVEL_HEIGHT)
        solution = FineTuned(Stub([quiet]), quiet_for=quiet_for)
        cell = Cell(seen=(glass(height=0.14),))
        result = answers(solution, cell)
        assert result.said_done
        assert result.answers == quiet_for
        # The answer that completed the spell is not carried out: it would not
        # touch a glass, so following it would spend arm seconds to change
        # nothing.
        assert len(cell.followed) == quiet_for - 1


def test_a_push_in_the_middle_of_a_spell_starts_the_count_again():
    quiet, push = flat_chunk(TRAVEL_HEIGHT), flat_chunk(PUSH_HEIGHT)
    solution = FineTuned(Stub([quiet, quiet, push, quiet, quiet, quiet]), quiet_for=3)
    result = answers(solution, Cell(seen=(glass(),)))
    assert result.said_done
    # Two quiet, a push, and then three more before the spell is long enough.
    assert result.answers == 6


def test_an_answer_that_would_sweep_a_tall_glass_is_not_quiet():
    """The tallest glass measured is what decides, not the height the jaw pushes at.

    A waypoint's height is the middle of the jaw and the hand hangs below it, so
    a path well clear of the pushing height can still drag the hand through the
    top of a glass. Such a path is not the policy saying it sees nothing to do.
    """
    tall = 0.22
    sweeping = flat_chunk(tall + JAW_HALF_HEIGHT - 0.005)
    solution = FineTuned(Stub([sweeping]), quiet_for=3)
    cell = Cell(seen=(glass(height=tall),))
    result = answers(solution, cell, seconds=60.0)
    assert not result.said_done, "a path through the top of a glass is not a declaration"
    assert len(cell.followed) > 3


def test_a_table_is_forgotten_between_tables():
    quiet = flat_chunk(TRAVEL_HEIGHT)
    solution = FineTuned(Stub([quiet]), quiet_for=3)
    for seed in (0, 1):
        cell = Cell(seen=(glass(),))
        result = clear_table(solution, seed=seed, seconds_left=120.0, cell=cell)
        # A quiet spell at the end of one table must not end the next one
        # before it has started, so each table takes the whole spell again.
        assert result.answers == 3
    assert solution.model.resets == 2


def test_the_first_answer_is_made_from_the_benchs_own_home_pose():
    solution = FineTuned(Stub([flat_chunk(TRAVEL_HEIGHT)]), quiet_for=3)
    answers(solution, Cell(seen=(glass(),)))
    assert solution.model.asked[0] == HOME


def test_why_the_cell_refused_is_counted_by_kind():
    solution = FineTuned(Stub([flat_chunk(PUSH_HEIGHT)]), quiet_for=3)
    solution.begin(0)
    for because in (
        "the cell would not drive the jaw into glass 2, which would tip",
        "the cell would not drive the jaw into glass 1, which would tip",
        "a waypoint is off the table",
    ):
        solution.answer(Look(picture=PICTURE, seen=(glass(),), jaw=HOME, seconds_left=100.0, refused=because))
    assert solution.summary()["refused_because"] == {"the tipping interlock": 2, "the bench": 1}


def test_the_answers_it_gave_are_summarised_for_the_record():
    solution = FineTuned(Stub([flat_chunk(PUSH_HEIGHT, across=0.2)]), quiet_for=3)
    answers(solution, Cell(seen=(glass(),)), seconds=30.0)
    summary = solution.summary()
    assert summary["quiet_answers_taken_as_done"] == 3
    assert summary["shape"]["answers"] > 0
    assert summary["shape"]["lowest_mm_median"] == pytest.approx(1000 * PUSH_HEIGHT, abs=0.1)
    assert summary["shape"]["across_mm_median"] == pytest.approx(200, abs=1)
    assert summary["looking_share"] == 0.0, "every answer here comes down to the pushing height"


def test_the_quiet_count_is_the_benchs_own_and_not_this_folders():
    """Every solution in problem 4 is stopped by one rule, so the count is taken as it comes."""
    from stopping import QUIET_ANSWERS

    solution = FineTuned(Stub([flat_chunk(TRAVEL_HEIGHT)]))
    assert solution.quiet_for == QUIET_ANSWERS
    assert solution.quiet.enough == QUIET_ANSWERS


# --------------------------------------------------------------- the walking


def test_each_walk_of_the_queue_gets_its_own_fitted_correction():
    """Three corrections, three walks, and one model held at a time."""
    from pathlib import Path

    import run

    made = []

    def fake(folder: Path, device):
        made.append(folder.name)
        return Stub([flat_chunk(TRAVEL_HEIGHT)])

    walks = run.Walks([Path("correction-0"), Path("correction-1")], None, 4, make=fake)
    first, second = walks(), walks()
    assert made == ["correction-0", "correction-1"]
    assert first is not second
    # The first walk's solution is let go of once the second starts, so three
    # walks never hold three models, and what it counted is kept.
    assert len(walks.summaries()) == 2
    assert [one["correction"] for one in walks.summaries()] == ["correction-0", "correction-1"]
    assert all(one["quiet_answers_taken_as_done"] == 4 for one in walks.summaries())


def test_a_table_the_arm_never_moved_on_is_not_counted():
    """The runner drops such a table, so a queue of one comes back empty and is skipped.

    It can happen with a full allowance and not only at the end of a budget: a
    policy whose every answer the cell refuses spends no arm time at all, and
    counting the table would put every glass on it among the glasses left
    crowded.
    """
    from pathlib import Path

    import run

    class Refusing(Cell):
        def follow(self, chunk: Chunk) -> Record:
            raise ValueError("a waypoint is off the table")

    walks = run.Walks(
        [Path("correction-0")], None, 3, make=lambda folder, device: Stub([flat_chunk(PUSH_HEIGHT)])
    )
    repeats, skipped = run.a_table_at_a_time(
        walks, range(1), room=2.0, runs=1, cell_for=lambda seed: Refusing(seen=(glass(),))
    )
    assert repeats.cards[0].results == []
    assert skipped == 1


def test_more_walks_than_corrections_come_round_again():
    from pathlib import Path

    import run

    walks = run.Walks([Path("correction-0")], None, 4, make=lambda folder, device: Stub([flat_chunk(0.3)]))
    walks(), walks()
    assert [one["correction"] for one in walks.summaries()] == ["correction-0", "correction-0"]


# --------------------------------------------------------------- the weights


def test_a_missing_correction_is_said_plainly_and_not_guessed_at(tmp_path):
    with pytest.raises(SystemExit, match="correction-0"):
        weights.fitted(1, folder=tmp_path)


def test_every_seed_has_its_own_folder():
    assert weights.correction(0) != weights.correction(1)
    assert weights.correction(2).name.endswith("2")
