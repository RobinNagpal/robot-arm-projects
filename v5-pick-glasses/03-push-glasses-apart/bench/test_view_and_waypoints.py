"""The four things the bench grew for solutions 3, 5 and 6.

The straight-down view, the waypoint path, the shared push budget and the
spread over several runs. Nothing here downloads anything or needs a GPU.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from work_cell.glasses.shapes import family
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.rack.layout import GLASS_ZONE

import bench
import top_view
from scoring import Repeats, Scorecard, spread


def _alone(kind, outline, x=0.48, y=-0.26):
    return bench.Bench(0, [SpawnedGlass("glass_0", kind, outline, (x, y, bench.TABLE_TOP_Z), 0.0)])


def _glasses(picture):
    """The glass pixels of a view: a glass's blue is at least its red, the table's never is."""
    return picture[:, :, 2].astype(int) >= picture[:, :, 0].astype(int)


# ------------------------------------------------------------- the top view


def test_the_view_is_the_shape_and_type_the_docstring_promises():
    picture = top_view.top_view(bench.Bench(bench.TEST_SEEDS))
    assert picture.shape == (*bench.TOP_VIEW_SIZE, 3)
    assert picture.dtype == np.uint8


def test_the_view_is_not_blank_and_shows_every_glass():
    table = bench.Bench(bench.TEST_SEEDS)
    picture = top_view.top_view(table)
    assert picture.std() > 10.0
    # One blob per glass is too much to ask of a crowded table, but each glass
    # must put some of its own colour where the view says it stands.
    for i in range(len(table.glasses)):
        row, column = top_view.to_pixel(*table.position(i))
        patch = _glasses(picture)[round(row) - 4 : round(row) + 5, round(column) - 4 : round(column) + 5]
        assert patch.any(), f"glass {i} is not in the view where to_pixel puts it"


def test_a_bare_table_has_no_glass_coloured_pixel():
    assert not _glasses(top_view.top_view(bench.Bench(0, []))).any()


def test_the_view_is_the_same_picture_on_the_same_table():
    first = top_view.top_view(bench.Bench(bench.TEST_SEEDS))
    again = top_view.top_view(bench.Bench(bench.TEST_SEEDS))
    assert np.array_equal(first, again)


@pytest.mark.parametrize("kind", bench.KINDS)
def test_to_pixel_lands_on_the_foot_of_a_glass_wherever_it_stands(kind):
    outline, _ = next(iter(family(kind, 1, seed=5)))
    for x, y in ((0.48, -0.26), (0.36, -0.40), (0.60, -0.12)):
        picture = top_view.top_view(_alone(kind, outline, x, y))
        row, column = top_view.to_pixel(x, y)
        assert _glasses(picture)[round(row), round(column)]


def test_to_pixel_and_to_table_are_each_other():
    for x, y in ((0.48, -0.26), (GLASS_ZONE[0], GLASS_ZONE[2]), (GLASS_ZONE[1], GLASS_ZONE[3])):
        back = top_view.to_table(*top_view.to_pixel(x, y))
        assert math.dist(back, (x, y)) < 1e-9


def test_the_frame_holds_the_whole_glass_zone():
    """A glass standing at the zone's edge is whole in the picture, not cut off."""
    tallest = max(
        (outline for kind in bench.KINDS for outline, _ in family(kind, 8, seed=1)),
        key=lambda outline: outline.total_height,
    )
    kind = "stemmed_glass"
    for x in GLASS_ZONE[:2]:
        for y in GLASS_ZONE[2:]:
            mask = _glasses(top_view.top_view(_alone(kind, tallest, x, y)))
            assert not (mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())


def test_rendering_is_charged_to_the_bench_and_not_to_the_solution():
    table = bench.Bench(bench.TEST_SEEDS)
    before = table.seconds
    top_view.top_view(table)
    assert table.seconds > before


# --------------------------------------------------------- waypoints


def _straight_push(table):
    seen = table.look()[0]
    radius = seen.widest / 2
    return bench.Push(0, (seen.x - radius - 0.01, seen.y), 0.0, radius + 0.04, 0.04, (0.0, 0.0))


@pytest.mark.parametrize("kind", bench.KINDS)
def test_a_chunk_and_the_push_it_came_from_end_in_the_same_place(kind):
    """The same motion through either door leaves the glass in the same spot."""
    for outline, _ in family(kind, 3, seed=2):
        pushed, followed = _alone(kind, outline), _alone(kind, outline)
        felt = pushed.push(_straight_push(pushed))
        assert felt.touched is not None
        path = pushed.records[0].waypoints
        same = followed.follow(bench.Chunk(0, path, (0.0, 0.0)))
        assert math.dist(pushed.position(0), followed.position(0)) < 0.002
        assert same.blocked == felt.blocked and same.jammed == felt.jammed
        assert abs(same.touched - felt.touched) < 0.002
        assert abs(same.pushed - felt.pushed) < 0.002


def test_both_paths_leave_the_same_kind_of_record():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    pushed, followed = _alone("straight_glass", outline), _alone("straight_glass", outline)
    pushed.push(_straight_push(pushed))
    followed.follow(bench.Chunk(0, pushed.records[0].waypoints, (0.0, 0.0)))
    one, two = pushed.records[0], followed.records[0]
    assert type(one) is type(two)
    assert one.push.glass == two.push.glass and one.push.aim == two.push.aim
    assert len(two.waypoints) > 1


def test_a_push_is_written_down_as_a_trajectory_a_policy_could_have_emitted():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    table = _alone("straight_glass", outline)
    table.push(_straight_push(table))
    path = table.records[0].waypoints
    assert 1 < len(path) <= bench.MAX_WAYPOINTS
    assert path[0].z == pytest.approx(bench.TRAVEL_HEIGHT)
    assert min(point.z for point in path) == pytest.approx(bench.PUSH_HEIGHT)
    assert all(bench.PUSH_HEIGHT - 1e-9 <= point.z <= bench.TRAVEL_HEIGHT + 1e-9 for point in path)


def test_a_chunk_can_be_given_as_a_policy_s_own_array():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    table = _alone("straight_glass", outline)
    table.push(_straight_push(table))
    path = table.records[0].waypoints
    array = np.array([[p.x, p.y, p.z, p.heading] for p in path])
    assert bench.Chunk.from_array(0, array, (0.0, 0.0)).waypoints == path


def test_a_chunk_that_comes_down_on_a_glass_reports_blocked():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    table = _alone("straight_glass", outline)
    seen = table.look()[0]
    down = [
        bench.Waypoint(seen.x, seen.y, bench.TRAVEL_HEIGHT, 0.0),
        bench.Waypoint(seen.x, seen.y, bench.PUSH_HEIGHT, 0.0),
    ]
    felt = table.follow(bench.Chunk(0, tuple(down), (0.0, 0.0)))
    assert felt.blocked and felt.touched is None and felt.pushed == 0.0


def test_a_chunk_that_touches_nothing_says_so():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    table = _alone("straight_glass", outline)
    away = [
        bench.Waypoint(0.36, -0.42, bench.TRAVEL_HEIGHT, 0.0),
        bench.Waypoint(0.36, -0.42, bench.PUSH_HEIGHT, 0.0),
        *(bench.Waypoint(0.36 + 0.001 * k, -0.42, bench.PUSH_HEIGHT, 0.0) for k in range(1, 21)),
    ]
    felt = table.follow(bench.Chunk(0, tuple(away), (0.0, 0.0)))
    assert not felt.blocked and felt.touched is None and not felt.jammed


@pytest.mark.parametrize(
    "waypoints",
    [
        (),
        (bench.Waypoint(0.48, -0.26, bench.PUSH_HEIGHT - 0.01, 0.0),),
        (bench.Waypoint(0.48, -0.26, bench.TRAVEL_HEIGHT + 0.01, 0.0),),
        (bench.Waypoint(9.0, -0.26, bench.PUSH_HEIGHT, 0.0),),
        tuple(
            bench.Waypoint(0.48, -0.26, bench.PUSH_HEIGHT, 0.0) for _ in range(bench.MAX_WAYPOINTS + 1)
        ),
    ],
)
def test_a_chunk_the_jaw_cannot_follow_is_refused_and_says_why(waypoints):
    table = bench.Bench(bench.TEST_SEEDS)
    with pytest.raises(ValueError):
        table.follow(bench.Chunk(0, waypoints, (0.0, 0.0)))


# ------------------------------------------------------------ the budget


def test_the_budget_is_one_number_in_the_bench():
    assert bench.PUSHES_PER_GLASS >= 1 and bench.PUSHES_PER_TABLE >= bench.PUSHES_PER_GLASS


def test_both_halves_of_the_budget_bind():
    """A run that keeps pushing is stopped per glass first, then per table."""
    table = bench.Bench(bench.TEST_SEEDS)
    spent: dict[int, int] = {}
    while len(table.records) < bench.PUSHES_PER_TABLE:
        free = [g for g in table.look() if spent.get(g.id, 0) < bench.PUSHES_PER_GLASS]
        if not free:
            break
        glass = free[0]
        table.push(bench.Push(glass.id, (glass.x - 0.08, glass.y), 0.0, 0.02, 0.005, (glass.x, glass.y)))
        spent[glass.id] = spent.get(glass.id, 0) + 1
    assert len(table.records) <= bench.PUSHES_PER_TABLE
    assert max(spent.values()) <= bench.PUSHES_PER_GLASS
    # The table ran out of pushes before every glass ran out of its own.
    assert len(table.records) == bench.PUSHES_PER_TABLE


# ------------------------------------------------------ repeats and compute


def _one_run(card, seeds):
    """A stand-in for a solution: one push, then rack whatever is there."""
    for seed in seeds:
        table = bench.Bench(seed)
        first = table.look()[0]
        table.push(bench.Push(first.id, (first.x - 0.08, first.y), 0.0, 0.05, 0.01, (first.x, first.y)))
        for glass in table.look():
            table.take(glass.id)
        card.scene(table, {}, seconds=table.seconds + 0.01)


def test_several_runs_report_a_spread():
    runs = Repeats()
    for shift in range(3):
        _one_run(runs.run(), [bench.TEST_SEEDS + shift, bench.TEST_SEEDS + shift + 1])
    result = runs.summary()
    assert result["runs"] == 3 and len(result["each"]) == 3
    band = result["spread"]["glasses_end.racked"]
    assert band["least"] <= band["median"] <= band["most"]
    assert band["sd"] > 0.0, "three different pairs of tables should not rack the same number"


def test_several_runs_are_saved_in_full_beside_their_spread(tmp_path):
    runs = Repeats()
    for shift in range(2):
        _one_run(runs.run(), [bench.TEST_SEEDS + shift])
    save = tmp_path / "results.json"
    runs.report(save)
    written = json.loads(save.read_text())
    assert written["runs"] == 2
    assert [run["scenes"] for run in written["each"]] == [1, 1]
    assert set(written["spread"]["pushes.total"]) == {"median", "sd", "least", "most"}
    # Every run reports its own time, so the spread carries the compute column.
    assert "seconds_per_push" in written["spread"]


def test_a_spread_over_one_run_is_zero_rather_than_missing():
    band = spread([{"pushes": {"total": 7}}])
    assert band["pushes.total"] == {"median": 7.0, "sd": 0.0, "least": 7.0, "most": 7.0}


def test_a_number_only_some_runs_report_is_left_out():
    assert "b" not in spread([{"a": 1, "b": 2}, {"a": 3}])


def test_the_time_per_push_is_the_thinking_and_not_the_physics():
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    table = _alone("straight_glass", outline)
    table.push(_straight_push(table))
    card = Scorecard()
    card.scene(table, {0: "no reason to push it"}, seconds=table.seconds + 0.2)
    assert card.summary()["seconds_per_push"] == pytest.approx(0.2, abs=0.05)


def test_a_run_that_was_not_timed_reports_no_time_at_all():
    table = bench.Bench(bench.TEST_SEEDS)
    card = Scorecard()
    card.scene(table, {glass.id: "untouched" for glass in table.look()})
    assert "seconds_per_push" not in card.summary()


def test_the_scorecard_still_writes_the_shape_the_two_built_solutions_committed(tmp_path):
    table = bench.Bench(bench.TEST_SEEDS)
    card = Scorecard()
    card.scene(table, {glass.id: "untouched" for glass in table.look()})
    save = tmp_path / "results.json"
    card.report(save)
    keys = set(card.summary())
    assert keys == {
        "scenes",
        "glasses",
        "crowded_at_start",
        "outcome",
        "glasses_end",
        "refused_because",
        "pushes",
    }
    assert Path(save).read_text().endswith("}\n")
