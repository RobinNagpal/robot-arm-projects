"""Tests for the wrapping around the fitted model, and for the borrowed wiring.

Nothing here is fitted and nothing here is physics. What is covered is the four
things that would be wrong *silently* -- each of them produces a run that a
scorecard would happily add up.

1. A path the bench would refuse. A network can answer with any number, so the
   pulling-in is the one thing between the model and a ``ValueError``.
2. Saying "done" too soon or never. The rule is borrowed from
   ``bench/stopping.py``, so what is tested here is that this folder feeds it
   the right thing and acts on its answer.
3. A glass index the bench raises on, which every path has to carry whether or
   not it is aimed at a glass.
4. The borrowed ACT wiring reading problem 4's chunk rather than problem 3's,
   which is the one way ``wiring.py`` can go wrong without saying so.

The paths are families rather than examples, as everything in this project is:
a wrapping that holds for a forty-millimetre push and fails for a hundred and
fifty is the exact fault a single case cannot catch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import chunks
import loading
import numpy as np
import readings
from clear import Imitation, _aim, _glass
from wiring import pictures, policy

from contract import Done, Look
from open_run import HOME, clear_table
from partners import (
    JAW_HALF_HEIGHT,
    MAX_WAYPOINTS,
    PUSH_HEIGHT,
    TRAVEL_HEIGHT,
    Chunk,
    Felt,
    Record,
    Seen,
    Waypoint,
)
from stopping import QUIET_ANSWERS, is_a_push
from wrist import WRIST_VIEW_SIZE

MIDDLE = (HOME.x, HOME.y)


def a_glass(at: tuple[float, float] = MIDDLE, *, number: int = 0, widest: float = 0.07) -> Seen:
    """One glass as a look reports it. These are measurements, not a size table."""
    return Seen(id=number, x=at[0], y=at[1], height=0.12, widest=widest, foot=0.06, standing=True)


def look_at(glasses: list[Seen], jaw: Waypoint = HOME, seconds: float = 240.0) -> Look:
    rows, columns = WRIST_VIEW_SIZE
    return Look(
        picture=np.zeros((rows, columns, 3), dtype=np.uint8),
        seen=tuple(glasses),
        jaw=jaw,
        seconds_left=seconds,
    )


def a_look_path(x: float = MIDDLE[0], y: float = MIDDLE[1]) -> np.ndarray:
    """A chunk that says "stand here": one waypoint at travel height, then padding."""
    return chunks.to_action([Waypoint(x, y, TRAVEL_HEIGHT, 0.5)])


def a_push_path(across: float, behind: float = 0.06) -> np.ndarray:
    """A chunk that comes down behind a glass and shoves it, in the teacher's own shape.

    Written in the glass's own frame, which is how a push is written now: the
    waypoints are measured from the glass being pushed, so ``(0, 0)`` is that
    glass and the path comes down ``behind`` millimetres short of it. ``clear.py``
    adds the glass's place back on before the answer goes to the bench.
    """
    heading = 0.0
    start = (-behind, 0.0)
    points = [Waypoint(*start, TRAVEL_HEIGHT, heading)]
    drops = max(1, math.ceil((TRAVEL_HEIGHT - PUSH_HEIGHT) / 0.01))
    for step in range(1, drops + 1):
        z = TRAVEL_HEIGHT - step * (TRAVEL_HEIGHT - PUSH_HEIGHT) / drops
        points.append(Waypoint(*start, z, heading))
    # A millimetre a waypoint, which is the speed the teacher pushes at, up to
    # the point where the whole path would not fit in a chunk. The longest push
    # tested here is longer than any the teacher makes, so it is spaced wider.
    steps = max(1, min(chunks.CHUNK - drops - 1, round((behind + across) / 0.001)))
    for step in range(1, steps + 1):
        gone = step * (behind + across) / steps
        points.append(
            Waypoint(
                start[0] + gone * math.cos(heading),
                start[1] + gone * math.sin(heading),
                PUSH_HEIGHT,
                heading,
            )
        )
    return chunks.to_action(points)


@dataclass
class Canned:
    """A model that answers from a list and repeats its last answer for ever.

    It stands in for a fitted one so that the wrapping can be tested without an
    hour of fitting. It takes the same two arguments a fitted model takes, and
    records them, because handing the model the wrong observation is one of the
    ways this folder could be quietly wrong.
    """

    answers: list[np.ndarray]
    asked: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)

    def chunk(self, picture: np.ndarray, state: np.ndarray | None = None) -> np.ndarray:
        self.asked.append((picture, state))
        return self.answers[min(len(self.asked) - 1, len(self.answers) - 1)]


@dataclass
class Told:
    """A gate that always decides the same thing, for testing the wrapping around it.

    It stands in for a fitted gate the way ``Canned`` stands in for a fitted
    policy, and it records what it was shown, because handing the gate the
    decision it is supposed to be making would be a quiet way for this folder to
    be wrong.
    """

    kind: int = readings.LOOK
    slot: int = readings.NO_GLASS
    asked: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)

    def decide(self, picture: np.ndarray, numbers: np.ndarray) -> tuple[int, int]:
        self.asked.append((picture, numbers))
        return self.kind, self.slot


def solution_with(answers: list[np.ndarray], kind: int = readings.LOOK, slot: int = readings.NO_GLASS):
    """A solution built from a canned policy and a gate that always says one thing."""
    return Imitation(Canned(answers), Told(kind, slot))


# ------------------------------------------------------- what the model is shown


def test_the_model_is_shown_the_picture_the_readings_and_the_pose():
    model, told = Canned([a_look_path()]), Told()
    solution = Imitation(model, told)
    look = look_at([a_glass(), a_glass((0.05, 0.6), number=1)])
    solution.answer(look)
    picture, state = model.asked[0]
    assert picture.shape == (*WRIST_VIEW_SIZE, 3)
    # The readings and the pose come first, exactly as the gate is shown them,
    # and the policy is shown the gate's decision after them.
    assert np.allclose(state[: readings.STATE_WIDTH], readings.to_state(look.jaw, look.seen))
    assert len(state) == readings.ASKED_WIDTH
    assert np.allclose(told.asked[0][1][: readings.STATE_WIDTH], state[: readings.STATE_WIDTH])


def test_two_stands_over_one_table_are_two_different_observations():
    """The camera rides on the arm, so where the jaw is standing is part of the look."""
    model = Canned([a_look_path()])
    solution = Imitation(model, Told())
    glasses = [a_glass()]
    solution.answer(look_at(glasses, HOME))
    solution.answer(look_at(glasses, Waypoint(0.1, 0.42, TRAVEL_HEIGHT, -1.0)))
    assert not np.allclose(model.asked[0][1], model.asked[1][1])


# ------------------------------------------------------------- the path that goes


def test_every_answer_is_a_path_the_bench_would_take():
    """Off the table, under the jaw's reach, too long: the three things follow() refuses."""
    for across in (0.002, 0.02, 0.05, 0.15):
        solution = solution_with([a_push_path(across)], readings.PUSH, 0)
        answer = solution.answer(look_at([a_glass()]))
        assert isinstance(answer, Chunk)
        assert 1 <= len(answer.waypoints) <= MAX_WAYPOINTS
        for point in answer.waypoints:
            assert PUSH_HEIGHT - 1e-9 <= point.z <= TRAVEL_HEIGHT + 1e-9


def test_a_wild_answer_is_pulled_in_and_counted():
    wild = a_push_path(0.04)
    wild[:, :2] += 9.0  # nine metres off the side of the table
    solution = solution_with([wild], readings.PUSH, 0)
    answer = solution.answer(look_at([a_glass()]))
    assert isinstance(answer, Chunk)
    assert solution.pulled_in == len(answer.waypoints)
    assert solution.chunks_pulled_in == 1


def test_a_path_names_a_glass_that_is_really_there():
    """``Chunk.glass`` is bookkeeping, and the bench still raises on an index that is not."""
    glasses = [a_glass((0.0, 0.5), number=3), a_glass((0.08, 0.62), number=7)]
    near_the_second = (Waypoint(0.08, 0.62, PUSH_HEIGHT, 0.0),)
    assert _glass(near_the_second, look_at(glasses)) == 7
    assert _glass(near_the_second, look_at([])) == 0


def test_the_aim_is_where_the_path_ends():
    """Problem 4 never reads an aim, and the bench still wants one."""
    points = (Waypoint(0.0, 0.5, PUSH_HEIGHT, 0.0), Waypoint(0.03, 0.5, PUSH_HEIGHT, 0.0))
    assert _aim(points) == (0.03, 0.5)


# --------------------------------------------------------------- saying it is done


def test_a_quiet_run_is_taken_as_the_model_saying_it_is_finished():
    solution = solution_with([a_look_path()])
    look = look_at([a_glass()])
    for _ in range(QUIET_ANSWERS - 1):
        assert isinstance(solution.answer(look), Chunk)
    done = solution.answer(look)
    assert isinstance(done, Done)
    assert done.why


def test_a_push_between_the_looks_starts_the_count_again():
    """Otherwise a solution that is working steadily would stop itself partway."""
    paths = [*[a_look_path()] * (QUIET_ANSWERS - 1), a_push_path(0.03), a_look_path()]
    # The gate asks for a push at the glass in the picture, so the push in the
    # middle of the spell is carried out as a push rather than raised.
    solution = Imitation(Canned(paths), Told(readings.PUSH, 0))
    look = look_at([a_glass()])
    for _ in range(QUIET_ANSWERS - 1):
        assert isinstance(solution.answer(look), Chunk)
    pushed = solution.answer(look)
    assert isinstance(pushed, Chunk)
    assert is_a_push(pushed)
    for _ in range(QUIET_ANSWERS - 1):
        assert isinstance(solution.answer(look), Chunk)
    assert isinstance(solution.answer(look), Done)


def test_begin_forgets_the_last_table_s_quiet_spell():
    solution = solution_with([a_look_path()])
    look = look_at([a_glass()])
    for _ in range(QUIET_ANSWERS - 1):
        solution.answer(look)
    solution.begin(1)
    assert isinstance(solution.answer(look), Chunk)


def test_the_quiet_rule_is_the_bench_s_own_and_is_not_overridden():
    """The number belongs to the bench, so that every solution reads the same one."""
    solution = solution_with([a_look_path()])
    assert solution.quiet_for == QUIET_ANSWERS


def test_a_sweep_the_gate_called_a_look_is_raised_rather_than_carried_out():
    """The failure that broke glasses on the first walks, and what now happens to it.

    The fingers hang ``JAW_HALF_HEIGHT`` below the number a waypoint carries, so
    a path that looks high in its own numbers can drag the hand through the tops
    of the glasses. The gate called this answer a look, and a look has to ride at
    travel height, so the answer is raised. The arm goes to the same place and
    touches nothing on the way.
    """
    sweeping_path = a_look_path()
    sweeping_path[:, 2] = JAW_HALF_HEIGHT + 0.15

    tall = Seen(id=0, x=MIDDLE[0], y=MIDDLE[1], height=0.22, widest=0.07, foot=0.05, standing=True)
    solution = solution_with([sweeping_path])
    answer = solution.answer(look_at([tall]))
    assert isinstance(answer, Chunk)
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)
    assert sum(solution.raised.values()) == 1
    assert solution.looks == 1
    # The tallest glass it has measured is still kept, because the stopping rule
    # is asked against it.
    assert solution.tallest == tall.height


# ----------------------------------------------------------- through the real loop


@dataclass
class Stubbed:
    """A cell with no physics, so the whole conversation can be run in a test.

    The same shape ``bench/test_open_run.py`` uses, and for the same reason: the
    behaviour being checked belongs to the solution, and the real cell needs a
    renderer and so a graphics context, which a test should not need.
    """

    on_table: list[Seen]
    followed: list[Chunk] = field(default_factory=list)

    def glasses(self) -> int:
        return len(self.on_table)

    def view(self, jaw: Waypoint) -> tuple[np.ndarray, tuple[Seen, ...]]:
        rows, columns = WRIST_VIEW_SIZE
        return np.zeros((rows, columns, 3), dtype=np.uint8), tuple(self.on_table)

    def truth(self) -> tuple[Seen, ...]:
        return tuple(self.on_table)

    def follow(self, chunk: Chunk) -> Record:
        self.followed.append(chunk)
        felt = Felt(blocked=False, touched=None, jammed=False, peak=0.0, pushed=0.0)
        # One entry a waypoint, which is how the bench writes a record down, plus
        # the lift home it makes for itself.
        return Record(chunk.as_push(), felt, chunk.aim, (*chunk.waypoints, chunk.waypoints[-1]))

    def toppled(self) -> int:
        return 0

    def pickable(self) -> int:
        return 0

    def charged(self) -> float:
        return 0.0


def test_a_model_that_only_looks_ends_the_table_by_saying_done():
    cell = Stubbed([a_glass()])
    solution = solution_with([a_look_path(0.0, 0.46)])
    result = clear_table(solution, 0, 240.0, cell=cell)
    assert result.said_done
    # The answer that completed the quiet spell is not carried out, so one fewer
    # path is followed than there were answers.
    assert len(cell.followed) == result.answers - 1


def test_a_model_that_keeps_pushing_is_stopped_by_the_clock():
    # An empty table, so that the cell's tipping interlock has nothing to refuse
    # and what is being tested is the clock and not the interlock.
    cell = Stubbed([])
    solution = solution_with([a_push_path(0.05)])
    result = clear_table(solution, 0, 20.0, cell=cell)
    assert not result.said_done
    assert result.arm_seconds > 0.0


# ----------------------------------------------------------- the borrowed wiring


def test_the_borrowed_wiring_reads_problem_four_s_chunk():
    """``policy`` is problem 3's file, and the chunk it sizes itself to has to be this one."""
    assert policy.CHUNK == chunks.CHUNK
    assert policy.ACTION_WIDTH == chunks.ACTION_WIDTH
    assert pictures.SEEN_SIZE[0] < WRIST_VIEW_SIZE[0]


def test_the_dataset_reader_needs_no_opinion_about_the_picture_s_size():
    """``loading`` is shared with solution 6, which reads the pictures at its own size."""
    assert "SEEN_SIZE" not in vars(loading)


def test_an_unfitted_model_answers_with_a_chunk_of_the_right_shape():
    """The end-to-end check on the borrowing: build the real model and ask it once.

    Unfitted, so the numbers are noise. The shape is the point: a model wired to
    problem 3's chunk would answer with five columns and a hundred and twenty
    rows, and the wrapping would then fail on the first table of a measurement
    run rather than here.
    """
    rows, columns = WRIST_VIEW_SIZE
    one = np.zeros((4, *pictures.SEEN_SIZE, 3), dtype=np.uint8)
    actions = np.zeros((4, chunks.CHUNK, chunks.ACTION_WIDTH), dtype=np.float32)
    scale = policy.Scale.of(one, actions)
    model = policy.Imitator.new("act", scale, seed=0, state_width=readings.STATE_WIDTH)
    answer = model.chunk(
        np.zeros((rows, columns, 3), dtype=np.uint8),
        readings.to_state(HOME, [a_glass()]),
    )
    assert answer.shape == (chunks.CHUNK, chunks.ACTION_WIDTH)
    points, _ = chunks.to_waypoints(answer)
    assert 1 <= len(points) <= chunks.CHUNK
