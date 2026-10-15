"""Tests for the borrowed model's side of problem 4, with no model and no physics.

Nothing here downloads a checkpoint. A test that needs two gigabytes off the
internet is not a test, and the thing worth testing is not the weights -- they
are somebody else's and they do not change -- but the wiring either side of
them: that a drawn trajectory becomes a path this cell will accept, that the
stopping rule is read off the shape of the answers and not off their quality,
and that nothing in the glass-index bookkeeping can crash a table.

So the model is a stand-in that answers with trajectories whose shape the test
chooses, and the cell is the one the loop's own tests use: no renderer, no
graphics context, no physics.

**The families, rather than the examples.** The two rules with any arithmetic
in them are proportions -- how low a chunk comes against the height a push
happens at, and how the model's six z-scores map into the box the bench will
accept -- and a proportion can hold for one trajectory and fail for a
differently shaped one. Both are checked over a drawn family that covers the
range the model's output really spans, including the ends where the clipping
bites.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
from as_downloaded import PARKED, REACHES_PUSH_HEIGHT, AsItDownloads, Shape
from borrowed import joining

from contract import Done, Look
from open_run import HOME, clear_table
from partners import JAW_HALF_HEIGHT, PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Seen, Waypoint
from stopping import QUIET_ANSWERS

# A picture of the shape the policy takes, which nothing in these tests reads.
PICTURE = np.zeros((384, 384, 3), dtype=np.uint8)


def glass(i: int = 0, x: float = 0.0, y: float = 0.5) -> Seen:
    """One reading of one glass, of a size nothing here depends on."""
    return Seen(id=i, x=x, y=y, height=0.14, widest=0.07, foot=0.055, standing=True)


def flat_path(z: float, points: int = 50, across: float = 0.2) -> np.ndarray:
    """A trajectory at one height, crossing ``across`` metres of table. (n, 4) jaw waypoints."""
    return np.stack(
        [
            np.linspace(-across / 2, across / 2, points),
            np.full(points, 0.5),
            np.full(points, z),
            np.zeros(points),
        ],
        axis=1,
    )


class Stub:
    """A stand-in for the downloaded policy: answers with the paths it is handed.

    It keeps every state it was asked with, because what the model is told
    about the jaw is one of the two things that change between problems 3 and
    4 and the solution has a switch for it.
    """

    def __init__(self, paths) -> None:
        self.paths = list(paths)
        self.asked: list[Waypoint] = []
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1

    def ask(self, picture: np.ndarray, jaw: Waypoint) -> np.ndarray:
        self.asked.append(jaw)
        # The last answer repeats forever, so a test need only write the part
        # of the conversation it is about.
        return self.paths[min(len(self.asked) - 1, len(self.paths) - 1)]


class Cell:
    """The work cell with nothing in it, answering ``open_run.Cell`` and no more.

    The same idea as the loop's own ``FakeCell``. It is written again here, in
    four lines, rather than imported from the bench's test file: a test file is
    not a module other folders import, and importing one would make this
    folder's tests fail the day the bench's tests were rearranged.
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

    def follow(self, chunk: Chunk):
        from partners import Felt, Record

        self.followed.append(chunk)
        felt = Felt(blocked=False, touched=None, jammed=False, peak=0.0, pushed=0.0)
        return Record(push=chunk.as_push(), felt=felt, landed=chunk.aim, waypoints=chunk.waypoints)

    def toppled(self) -> int:
        return self.fell

    def pickable(self) -> int:
        return self.room

    def charged(self) -> float:
        return 0.0


# ------------------------------------------------------------------ the join, over a family


def drawn_actions(seed: int, points: int = 50) -> np.ndarray:
    """A chunk of the model's own output: six z-scores a waypoint, spread as the model's are.

    The model emits normalised actions, so a standard normal is the honest
    draw, and the family deliberately runs past the edge of the box the
    reading can express so that the clipping is covered rather than avoided.
    """
    rng = random.Random(seed)
    return np.array([[rng.gauss(0.0, 1.6) for _ in range(joining.SLOTS)] for _ in range(points)])


@pytest.mark.parametrize("seed", range(40))
def test_every_drawn_chunk_is_one_the_cell_could_follow(seed: int) -> None:
    """Whatever the model answers, the path handed to the bench is inside the box.

    This is the join's one hard requirement and it is problem 3's, unchanged.
    If it failed, the loop would count the answer as refused by the bench and
    the model would be marked for a fault in the reading of its output.
    """
    path = joining.to_jaw(drawn_actions(seed))
    assert path.shape == (50, 4)
    assert np.all(path[:, 2] >= PUSH_HEIGHT - 1e-9)
    assert np.all(path[:, 2] <= TRAVEL_HEIGHT + 1e-9)
    assert np.all(np.abs(path[:, 3]) <= math.pi + 1e-9)


@pytest.mark.parametrize("seed", range(40))
def test_the_shape_of_an_answer_is_measured_in_millimetres(seed: int) -> None:
    """``Shape`` reports the three numbers problem 3 reports, in the same units."""
    path = joining.to_jaw(drawn_actions(seed))
    shape = Shape()
    shape.saw(path)
    summary = shape.summary()
    assert summary["answers"] == 1
    assert summary["lowest_mm_median"] == pytest.approx(1000 * path[:, 2].min(), abs=0.05)
    steps = np.hypot(np.diff(path[:, 0]), np.diff(path[:, 1]))
    assert summary["across_mm_median"] == pytest.approx(1000 * steps.sum(), abs=0.05)
    # A path that never comes down cannot have touched anything, and the share
    # has to agree with the stopping rule's own test of the same path.
    reaching = path[:, 2].min() <= REACHES_PUSH_HEIGHT
    assert summary["share_reaching_the_table"] == (1.0 if reaching else 0.0)


# ------------------------------------------------------------------ the stopping rule


@pytest.mark.parametrize("height", [PUSH_HEIGHT, PUSH_HEIGHT + 0.0005, 0.10, 0.18, 0.25])
def test_a_table_ends_only_after_enough_answers_that_could_not_touch_a_glass(height: float) -> None:
    """One answer decides nothing; ``QUIET_ANSWERS`` of them end the table.

    The family is heights either side of what the hand can reach, because that
    is the whole of the rule: a path low enough for any part of the hand to
    meet a glass is the policy acting, and one above everything on the table is
    the policy saying it sees nothing to do.

    The height that divides the two is not the height the jaw pushes at. A
    waypoint's number is the middle of the jaw and the fingers hang
    ``JAW_HALF_HEIGHT`` below it, so a path clearing the pushing height can
    still sweep a glass standing taller than that. The rule was corrected after
    a run broke a glass while every one of its answers was counted as quiet.
    """
    seen = glass()
    solution = AsItDownloads(Stub([flat_path(height)]))
    solution.begin(0)
    answers = []
    for _ in range(QUIET_ANSWERS + 1):
        answer = solution.answer(Look(picture=PICTURE, seen=(seen,), jaw=HOME, seconds_left=600.0))
        answers.append(answer)
        if isinstance(answer, Done):
            break

    could_touch = height - JAW_HALF_HEIGHT <= max(seen.height, PUSH_HEIGHT) + 0.001
    if could_touch:
        assert not any(isinstance(a, Done) for a in answers)
    else:
        assert isinstance(answers[-1], Done)
        assert len(answers) == QUIET_ANSWERS
        assert answers[-1].why


def test_one_push_among_the_quiet_answers_starts_the_count_again() -> None:
    """The rule is a run of quiet answers, not a total of them."""
    high, low = flat_path(0.25), flat_path(PUSH_HEIGHT)
    solution = AsItDownloads(Stub([high, high, low, high, high, high]))
    solution.begin(0)
    look = Look(picture=PICTURE, seen=(glass(),), jaw=HOME, seconds_left=600.0)
    answers = [solution.answer(look) for _ in range(5)]
    assert not any(isinstance(a, Done) for a in answers)
    assert isinstance(solution.answer(look), Done)


def test_a_new_table_starts_with_a_clean_count() -> None:
    """A quiet spell at the end of one table must not end the next one early."""
    solution = AsItDownloads(Stub([flat_path(0.25)]))
    look = Look(picture=PICTURE, seen=(glass(),), jaw=HOME, seconds_left=600.0)

    solution.begin(0)
    for _ in range(QUIET_ANSWERS - 1):
        assert isinstance(solution.answer(look), Chunk)

    solution.begin(1)
    assert solution.model.resets == 2
    assert isinstance(solution.answer(look), Chunk)


# ------------------------------------------------------------------ the bookkeeping


def test_a_look_that_shows_no_glass_still_produces_a_path() -> None:
    """The camera is on the arm now, so a look can be of bare table.

    Problem 3 could not meet this -- its camera saw the whole table -- and the
    glass a ``Chunk`` carries has to name a glass that is on the table. Nothing
    scores it here, but a crash would end the table.
    """
    solution = AsItDownloads(Stub([flat_path(PUSH_HEIGHT)]))
    solution.begin(0)
    answer = solution.answer(Look(picture=PICTURE, seen=(), jaw=HOME, seconds_left=600.0))
    assert isinstance(answer, Chunk)
    assert answer.glass == 0


def test_the_glass_named_is_the_one_last_seen_when_this_look_shows_nothing() -> None:
    """A path is named after the last look that showed something, not after glass zero."""
    solution = AsItDownloads(Stub([flat_path(PUSH_HEIGHT)]))
    solution.begin(0)
    seen = (glass(3, x=0.0, y=0.5),)
    first = solution.answer(Look(picture=PICTURE, seen=seen, jaw=HOME, seconds_left=600.0))
    blind = solution.answer(Look(picture=PICTURE, seen=(), jaw=HOME, seconds_left=600.0))
    assert first.glass == 3
    assert blind.glass == 3


def test_the_arm_time_split_counts_a_high_path_as_looking() -> None:
    """The split goes by whether a path comes down to the pushing height, and by nothing else."""
    solution = AsItDownloads(Stub([flat_path(0.25), flat_path(PUSH_HEIGHT)]))
    solution.begin(0)
    look = Look(picture=PICTURE, seen=(glass(),), jaw=HOME, seconds_left=600.0)
    solution.answer(look)
    assert solution.look_seconds > 0.0
    assert solution.push_seconds == 0.0
    solution.answer(look)
    assert solution.push_seconds > 0.0


# ------------------------------------------------------------------ the state


def test_the_state_the_model_is_told_is_where_the_jaw_really_is() -> None:
    """Problem 4's whole difference at the state input: the pose varies and is in range."""
    solution = AsItDownloads(Stub([flat_path(0.25)]))
    solution.begin(0)
    jaw = Waypoint(x=0.05, y=0.45, z=0.12, heading=0.3)
    solution.answer(Look(picture=PICTURE, seen=(glass(),), jaw=jaw, seconds_left=600.0))
    assert solution.model.asked[-1] == jaw
    # In range rather than pinned at the edge, which is what problem 3 could
    # never achieve: the height slot is strictly inside the box.
    state = joining.to_state(jaw)
    assert abs(state[joining.UP]) < joining.ACTION_SPAN


def test_pinned_hands_the_model_problem_threes_parked_pose() -> None:
    """The sensitivity check, which is what tells the picture and the state apart."""
    solution = AsItDownloads(Stub([flat_path(0.25)]), pinned=True)
    solution.begin(0)
    jaw = Waypoint(x=0.05, y=0.45, z=0.12, heading=0.3)
    solution.answer(Look(picture=PICTURE, seen=(glass(),), jaw=jaw, seconds_left=600.0))
    told = solution.model.asked[-1]
    assert (told.x, told.y, told.z) == pytest.approx(PARKED)
    assert told.heading == jaw.heading
    # Above travel height, so the height slot clips to the top of its range.
    assert told.z > TRAVEL_HEIGHT
    assert joining.to_state(told)[joining.UP] == pytest.approx(joining.ACTION_SPAN)


# ------------------------------------------------------------------ one whole table


def test_a_table_of_high_answers_is_declared_finished_and_costs_a_few_seconds() -> None:
    """The run the result is expected to be: the model answers high, so the table ends at once.

    This is the loop and the solution together, which is the only place the
    two meet, and it is also the shape of the measured result: a policy whose
    chunks never come down says it is done after ``QUIET_ANSWERS`` answers and
    the table is left as it was found.
    """
    cell = Cell(seen=(glass(0, 0.0, 0.5), glass(1, 0.03, 0.5)), pickable=1)
    solution = AsItDownloads(Stub([flat_path(0.25)]))
    result = clear_table(solution, seed=0, seconds_left=600.0, cell=cell)

    assert result.said_done
    assert result.answers == QUIET_ANSWERS
    # Two paths carried out, because the third is the declaration itself.
    assert len(cell.followed) == QUIET_ANSWERS - 1
    assert result.toppled == 0
    assert result.pickable_at_end == 1
    assert result.unfinished
    assert 0.0 < result.arm_seconds < 60.0
