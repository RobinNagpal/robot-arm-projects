"""The quick checks on the parts both rungs of this solution stand on.

No weights and no network: what is checked here is the shading, the camera the
two rungs share, the split between training and held-out scenes, the two kinds
of mask, the arithmetic that turns a mask into a place and a width, the
keeper's own arithmetic and its two thresholds, and that both rungs really do
answer one interface.

Every check that involves a glass runs over a family of them rather than one,
because a rule that holds for one glass of a kind and fails for a differently
proportioned one is the failure this project exists to prevent.
"""

import inspect
import math
from pathlib import Path

import numpy as np
import pytest
import reports
import sam3_words
import sam_keeper
import torch
import train
import weights
from work_cell.arm.dimensions import SURVEY_HEIGHT, survey_stations
from work_cell.glasses.shapes import family
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

import data
import device
import masks_to_glasses
import pictures
import render

# How far a place read off a mask may sit from where the glass really stands,
# and how far its width may be out. The tolerances ../01-rules-on-the-table's
# own tests hold that arithmetic to, since it is the same arithmetic.
PLACE_TOLERANCE = 0.002
WIDTH_TOLERANCE = 0.003

HERE = Path(__file__).parent


def _one(kind, outline, x, y):
    return render.Glass(kind, x, y, outline.height, outline.radius)


def _middle_station():
    """The station in the middle of the survey, and the point on the table below it."""
    pose = data.poses()[len(data.poses()) // 2]
    return pose, data.under(pose)


def test_a_device_is_chosen_and_it_is_one_this_machine_has():
    picked = device.pick()
    assert picked.type == ("mps" if torch.backends.mps.is_available() else "cpu")
    assert device.describe(picked)


# ------------------------------------------------------------------ the camera


def test_the_survey_stands_at_the_cells_own_height_and_takes_three_pictures():
    for pose in data.poses():
        eye = pose[:3, 3]
        assert eye[2] == pytest.approx(TABLE_TOP_Z + SURVEY_HEIGHT)
        # Straight down: the view axis is the third column of the pose.
        assert pose[:3, 2] == pytest.approx([0.0, 0.0, -1.0])
    assert len(data.stations()) == 3
    assert len(data.poses()) == len(data.stations())


def test_the_stations_come_from_the_shared_frame_and_not_the_whole_frame():
    # The frame less what a survey loses is the cell's own arithmetic, and it is
    # what makes the survey three pictures. Handed the whole frame instead,
    # survey_stations answers one, which would be the wrong survey.
    assert data.shared()[0] < data.frame()[0] and data.shared()[1] < data.frame()[1]
    assert np.allclose(data.stations(), survey_stations(GLASS_ZONE, data.shared()))
    assert len(survey_stations(GLASS_ZONE, data.frame())) == 1


def test_every_station_looks_at_part_of_the_zone_and_they_are_not_the_same_place():
    places = [data.under(pose) for pose in data.poses()]
    assert len(set(places)) == len(places)
    for x, y in places:
        assert data.in_zone(x, y)


def test_one_picture_from_the_cells_height_does_not_hold_the_whole_zone():
    """The measured reason the survey is three pictures rather than one.

    A rim leans away from the point below the camera, so a tall glass at the far
    side of the zone is cut off at the frame edge even though the table under it
    is in shot. From render.TOP_HEIGHT, which is higher, nothing is cut.
    """
    kind = "stemmed_glass"
    tallest = max((o for o, _ in family(kind, 40, seed=3)), key=lambda o: o.total_height)
    corner = _one(kind, tallest, GLASS_ZONE[1], GLASS_ZONE[3])

    def touches_edge(pose):
        mask = render.render([corner], pose).ids == 1
        return mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()

    assert all(touches_edge(pose) for pose in data.poses())
    assert not touches_edge(render.top_pose())


# ----------------------------------------------------------------- the pictures


def test_a_shaded_picture_is_a_three_channel_eight_bit_picture():
    picture = data.spawned(render.TEST_SEEDS).sights[0].picture
    image = pictures.shade(picture)
    assert image.shape == (render.HEIGHT, render.WIDTH, 3)
    assert image.dtype == np.uint8
    assert (image[:, :, 0] == image[:, :, 1]).all()
    assert (image[:, :, 1] == image[:, :, 2]).all()
    assert image.min() >= pictures.BACKGROUND and image.max() <= 255
    # Shading twice gives the same bytes, so a run can be repeated.
    assert (pictures.shade(picture) == image).all()


def test_near_is_light_and_far_is_dark():
    picture = data.spawned(render.TEST_SEEDS).sights[0].picture
    depth, grey = picture.depth, pictures.grey(picture)
    hit = np.isfinite(depth)
    order = np.argsort(depth[hit], kind="stable")
    assert (np.diff(grey[hit][order].astype(int)) <= 0).all()


def test_a_ray_that_hit_nothing_shades_below_every_surface():
    picture = data.spawned(render.TEST_SEEDS).sights[0].picture
    # A picture past the edge of the table, which is what leaves rays hitting
    # nothing. Over the zone the table fills the frame, so this makes them.
    depth = picture.depth.copy()
    depth[:20] = np.inf
    grey = pictures.grey(render.Picture(depth, picture.ids, picture.camera_to_world))
    assert (grey[:20] == pictures.BACKGROUND).all()
    assert grey[20:].min() >= pictures.DARKEST > pictures.BACKGROUND


# ------------------------------------------------------------------ the scenes


def test_training_and_held_out_seeds_cannot_overlap():
    training, held_out = data.training_seeds(60), data.held_out_seeds(60)
    assert not set(training) & set(held_out)
    assert max(training) < render.TEST_SEEDS <= min(held_out)
    with pytest.raises(ValueError):
        data.training_seeds(10, start=render.TEST_SEEDS - 5)
    with pytest.raises(ValueError):
        data.held_out_seeds(10, start=render.TEST_SEEDS - 1)


def test_a_training_run_draws_both_kinds_of_scene():
    drawn = list(data.training(4))
    assert len(drawn) == 4
    assert data.how_many_crowded(4) == sum(example.crowded for example in drawn)
    for example in drawn:
        assert example.glasses
        assert len(example.sights) == len(data.stations())
        assert all(data.in_zone(glass.x, glass.y) for glass in example.glasses)


def test_a_whole_glass_mask_contains_the_visible_one():
    # Four scenes is all four kinds, because render.scene picks the kind by seed.
    for example in data.training(len(render.KINDS), share=0.0):
        for sight in example.sights:
            assert sight.masks(amodal=False) is sight.visible
            assert sight.masks(amodal=True) is sight.whole
            for visible, whole in zip(sight.visible, sight.whole, strict=True):
                assert not (visible & ~whole).any()


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_crowded_scene_really_does_hide_one_glass_behind_another(kind):
    # The case an amodal rung exists for. A spawned layout keeps glasses far enough
    # apart that it almost never happens, so it is built on purpose.
    example = data.crowded(render.KINDS.index(kind))
    assert example.kind == kind
    hidden = sum(
        int((whole & ~visible).sum())
        for sight in example.sights
        for whole, visible in zip(sight.whole, sight.visible, strict=True)
    )
    assert hidden > 0


# -------------------------------------------------- masks into places and widths


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_lone_glasss_place_and_width_are_read_back_off_its_mask(kind):
    # Standing under the camera, where nothing leans out of the frame: what is
    # being checked is the arithmetic, not what the survey height costs.
    pose, below = _middle_station()
    for outline, _ in family(kind, 10, seed=11):
        glass = _one(kind, outline, *below)
        picture = render.render([glass], pose)
        found = masks_to_glasses.one_glass(picture, picture.ids == 1)
        assert found is not None
        assert math.dist((found.x, found.y), below) < PLACE_TOLERANCE
        assert abs(found.width - 2 * glass.max_radius) < WIDTH_TOLERANCE


def test_a_mask_with_nothing_in_it_is_not_a_glass():
    picture = data.spawned(render.TEST_SEEDS).sights[0].picture
    empty = np.zeros(picture.ids.shape, dtype=bool)
    assert masks_to_glasses.one_glass(picture, empty) is None
    assert masks_to_glasses.to_glasses(picture, [empty, empty]) == []


def _hiding(kind):
    """A tall glass near the camera and a short one behind it, as the amodal case."""
    pose, below = _middle_station()
    drawn = [outline for outline, _ in family(kind, 40, seed=5)]
    near = _one(kind, max(drawn, key=lambda o: o.total_height), below[0] + 0.03, below[1])
    far = _one(kind, min(drawn, key=lambda o: o.total_height), below[0] + 0.10, below[1])
    picture = render.render([near, far], pose)
    whole = render.render([far], pose).ids == 1
    return picture, far, whole, picture.ids == 2


@pytest.mark.parametrize("kind", render.KINDS)
def test_what_a_nearer_glass_hides_is_in_the_whole_mask_and_not_the_visible_one(kind):
    _, _, whole, visible = _hiding(kind)
    assert not (visible & ~whole).any()
    assert whole.sum() > visible.sum()


@pytest.mark.parametrize("kind", render.KINDS)
def test_the_pixels_a_mask_only_asserts_are_kept_out_of_the_arithmetic(kind):
    """Solution 10's completion must not be read as if it were a depth reading.

    The pixels a whole outline adds carry the depth of the glass in front, so
    feeding them in puts the fitted place on that other glass. Naming them makes
    the whole outline answer what the visible pixels answer, which is the point:
    the completion says how far the glass reaches, never how far away it is.
    """
    picture, glass, whole, visible = _hiding(kind)
    truth = (glass.x, glass.y)
    asserted = whole & ~visible

    seen = masks_to_glasses.one_glass(picture, visible)
    poisoned = masks_to_glasses.one_glass(picture, whole)
    repaired = masks_to_glasses.one_glass(picture, whole, asserted)
    assert seen is not None and poisoned is not None and repaired is not None

    assert math.dist((repaired.x, repaired.y), truth) == pytest.approx(math.dist((seen.x, seen.y), truth))
    assert math.dist((poisoned.x, poisoned.y), truth) > math.dist((repaired.x, repaired.y), truth)
    # Only the pixels whose depth reading was used are reported.
    assert len(repaired.pixels) == len(seen.pixels)


def test_a_glass_seen_from_several_stations_is_reported_once():
    example = data.spawned(render.TEST_SEEDS)
    index = 0
    seen = [
        masks_to_glasses.one_glass(sight.picture, sight.picture.ids == index + 1) for sight in example.sights
    ]
    seen = [found for found in seen if found is not None]
    assert len(seen) > 1, "the stations overlap, so one glass should be in more than one picture"
    assert len(masks_to_glasses.one_per_place(seen, data.widths(example.kind)[0])) == 1


def test_a_glasss_pixels_land_on_that_glass_in_the_picture_the_scorecard_reads():
    example = data.spawned(render.TEST_SEEDS + 1)
    for index in range(len(example.glasses)):
        for sight in example.sights:
            mask = sight.picture.ids == index + 1
            if mask.sum() < masks_to_glasses.MIN_PIXELS:
                continue
            found = masks_to_glasses.one_glass(sight.picture, mask)
            pixels = data.in_reference(sight.picture, found.pixels, example.reference)
            ids = example.reference.ids[pixels[:, 0], pixels[:, 1]]
            assert (ids == index + 1).mean() > 0.9


# ---------------------------------------------------------------- one interface


def test_every_solution_here_is_one_interface():
    from importlib import import_module

    for name, solution in train.SOLUTIONS.items():
        module = import_module(solution.module)
        fit = inspect.signature(module.fit)
        assert list(fit.parameters) == ["examples", "amodal", "save"], name
        assert fit.parameters["amodal"].kind is inspect.Parameter.KEYWORD_ONLY
        assert fit.parameters["save"].kind is inspect.Parameter.KEYWORD_ONLY
        find = inspect.signature(module.Finder.find)
        assert list(find.parameters) == ["self", "picture", "kind"], name
        assert list(inspect.signature(module.load).parameters) == ["save"], name


def test_only_the_dispatch_table_knows_the_solutions_apart():
    """No `if solution == ...` anywhere else: a module is told what to do, not who it is."""
    for source in sorted(HERE.glob("*.py")):
        if source.name in ("train.py", "test_keeper.py"):
            continue
        text = source.read_text()
        for name in train.SOLUTIONS:
            for quoted in (f'"{name}"', f"'{name}'"):
                assert quoted not in text, f"{source.name} names {name}"


# ------------------------------------------------- the keeper, with no weights


def _two_glasses(kind, apart=0.10):
    """Two glasses of one kind standing ``apart`` metres either side of the middle station."""
    pose, below = _middle_station()
    drawn = [outline for outline, _ in family(kind, 20, seed=7)]
    left = _one(kind, drawn[0], below[0] - apart / 2, below[1])
    right = _one(kind, drawn[1], below[0] + apart / 2, below[1])
    return render.render([left, right], pose), pose


def test_the_keeper_is_shown_eight_measurements_and_they_are_the_eight_named():
    assert len(sam_keeper.MEASUREMENTS) == len(set(sam_keeper.MEASUREMENTS)) == 8


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_proposal_is_measured_into_those_eight_numbers(kind):
    """The measuring, run on true masks so that no model has to be downloaded.

    What is checked is that every one of the eight is a length, a count or a
    ratio of the size it claims to be: a glass stands clear of the table, its
    footprint falls inside the range its kind allows, and it is rounder than
    half, whichever kind it is.
    """
    picture, _ = _two_glasses(kind)
    masks = np.stack([picture.ids == 1, picture.ids == 2])
    ones = np.ones(len(masks))
    proposals = sam_keeper._proposals(picture, kind, masks, ones, ones, ones.astype(int))

    assert len(proposals) == 2
    for proposal in proposals:
        width, roundness, above, out, votes, step, area, nesting = proposal.features
        assert proposal.features.shape == (len(sam_keeper.MEASUREMENTS),)
        assert 0.0 <= width <= 1.0
        assert 0.5 < roundness <= 1.0
        assert above > 0.0
        assert 0.0 < out < max(data.frame())
        assert votes == 1
        assert 0.0 <= step <= 1.0
        assert area > 0.0
        assert nesting == 0.0


def test_a_part_inside_a_whole_declares_itself_in_the_containment_measurement():
    """A rim sits inside its glass, and one count read both ways separates them."""
    kind = "straight_glass"
    picture, _ = _two_glasses(kind)
    glass = picture.ids == 1
    rows, columns = np.nonzero(glass)
    part = np.zeros_like(glass)
    # The top half of that glass's pixels: entirely inside it, and not the whole.
    part[rows[rows < (rows.min() + rows.max()) // 2], columns[rows < (rows.min() + rows.max()) // 2]] = True

    masks = np.stack([glass, part])
    ones = np.ones(len(masks))
    whole, inside = sam_keeper._proposals(picture, kind, masks, ones, ones, ones.astype(int))
    assert inside.features[-1] > 0, "the part is inside something"
    assert whole.features[-1] < 0, "the whole holds something"


def test_how_round_a_shape_is_tells_a_filled_disc_from_a_ring():
    size = 200
    rows, columns = np.indices((size, size))
    away = np.hypot(rows - size / 2, columns - size / 2)
    disc = away < 60
    ring = disc & (away > 45)
    assert sam_keeper._roundness(disc) == pytest.approx(1.0, abs=0.1)
    assert sam_keeper._roundness(ring) < 0.5
    assert sam_keeper._roundness(np.zeros((size, size), dtype=bool)) == 0.0


def test_the_same_region_arriving_many_times_is_kept_once_and_counted():
    masks = np.zeros((3, 40, 40), dtype=bool)
    masks[0, 5:25, 5:25] = True  # one region
    masks[1, 6:26, 6:26] = True  # the same region, a prompt or two over
    masks[2, 30:38, 30:38] = True  # somewhere else entirely
    kept, votes = sam_keeper._deduplicate(masks, np.array([0.9, 0.8, 0.7]))
    assert kept == [0, 2]
    assert list(votes) == [2, 1]
    assert sam_keeper._deduplicate(np.zeros((0, 40, 40), dtype=bool), np.zeros(0))[0] == []


@pytest.mark.parametrize("kind", render.KINDS)
def test_the_three_answers_come_out_of_the_truth_by_arithmetic(kind):
    picture, _ = _two_glasses(kind)
    visible = [picture.ids == 1, picture.ids == 2]
    assert sam_keeper.label(visible[0], visible) == sam_keeper.ONE_GLASS
    assert sam_keeper.label(visible[0] | visible[1], visible) == sam_keeper.MORE_THAN_ONE
    assert sam_keeper.label(np.zeros_like(visible[0]), visible) == sam_keeper.DROP
    # The table holds both glasses and is mostly not them, which is the case
    # the second half of the label exists for.
    assert sam_keeper.label(np.ones_like(visible[0]), visible) == sam_keeper.DROP


def test_the_two_thresholds_leave_a_band_that_means_cannot_tell():
    def chance(one_glass, more=0.0):
        return np.array([1.0 - one_glass - more, one_glass, more])

    assert sam_keeper.verdict(chance(0.95)) == sam_keeper.KEEP
    assert sam_keeper.verdict(chance(sam_keeper.SURE_ONE_GLASS)) == sam_keeper.KEEP
    assert sam_keeper.verdict(chance(0.5)) == sam_keeper.UNSURE
    assert sam_keeper.verdict(chance(sam_keeper.SURE_NOT_ONE_GLASS)) == sam_keeper.REJECT
    assert sam_keeper.verdict(chance(0.1)) == sam_keeper.REJECT
    # More than one glass is a different thing to do next, not a doubtful glass,
    # so it is answered before either threshold is looked at.
    assert sam_keeper.verdict(chance(0.4, more=0.55)) == sam_keeper.SPLIT


def test_the_keeper_prints_its_inputs_beside_its_answer():
    """The document's headline claim for this solution, checked as code."""
    features = np.arange(len(sam_keeper.MEASUREMENTS), dtype=float)
    chance = np.array([0.02, 0.95, 0.03])
    lines = sam_keeper.explanation(features, chance)

    assert len(lines) == len(sam_keeper.MEASUREMENTS) + 1
    for name, line in zip(sam_keeper.MEASUREMENTS, lines, strict=False):
        assert name in line
    assert sam_keeper.verdict(chance) in lines[-1]
    for answer in sam_keeper.ANSWERS:
        assert answer in lines[-1]


def test_the_keeper_has_no_amodal_target_and_refuses_one():
    with pytest.raises(ValueError):
        sam_keeper.fit([], amodal=True, save=HERE / "weights" / "never-written.pt")


def test_too_few_of_an_answer_to_calibrate_on_is_refused_rather_than_guessed():
    enough = np.array([0, 0, 1, 1, 2, 2])
    assert sam_keeper._calibration(enough) == ("sigmoid", 2)
    with pytest.raises(RuntimeError):
        sam_keeper._calibration(np.array([0, 0, 1, 1, 2]))


def test_the_grid_is_fine_enough_for_the_narrowest_glass_of_the_kind():
    for kind in render.KINDS:
        spacing = sam_keeper.prompt_spacing(kind)
        across = data.widths(kind)[0] / (data.frame()[0] / render.WIDTH)
        assert spacing >= 1
        assert across / spacing >= sam_keeper.POINTS_ACROSS_SMALLEST
    inside = np.zeros((render.HEIGHT, render.WIDTH), dtype=bool)
    inside[100:140, 100:140] = True
    points = sam_keeper._grid(10, inside=inside)
    assert points and all(inside[int(row), int(column)] for column, row in points)


# ------------------------------------------- the arithmetic that has last word


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_width_no_glass_of_the_kind_could_have_is_refused_whatever_named_it(kind):
    picture, _ = _two_glasses(kind)
    pair = (picture.ids == 1) | (picture.ids == 2)
    kept, doubts = reports.believable(picture, [pair], kind)
    assert kept == []
    assert doubts == [reports.TOO_WIDE]

    kept, doubts = reports.believable(picture, [picture.ids == 1], kind)
    assert len(kept) == 1 and doubts == []
    assert reports.legal(kept[0], data.widths(kind))


def test_a_mask_too_small_to_fit_anything_to_is_not_a_report_at_all():
    picture, _ = _two_glasses("straight_glass")
    empty = np.zeros(picture.ids.shape, dtype=bool)
    assert reports.believable(picture, [empty], "straight_glass") == ([], [])


def test_two_reports_at_one_place_are_one_glass_reported_twice():
    """The same glass arriving twice, which is what a mouth kept beside its glass is."""
    kind = "straight_glass"
    picture, _ = _two_glasses(kind)
    glass = picture.ids == 1
    again = np.roll(glass, 2, axis=1)  # the same region, two pixels over

    assert len(reports.believable(picture, [glass], kind)[0]) == 1
    assert len(reports.believable(picture, [again], kind)[0]) == 1
    assert len(reports.believable(picture, [glass, again], kind)[0]) == 1


# ------------------------------------------------------- the word rung's shape


def test_the_word_rung_fits_nothing_and_says_so_rather_than_writing_a_file():
    save = HERE / "weights" / "never-written.pt"
    with pytest.raises(SystemExit):
        sam3_words.fit([], amodal=False, save=save)
    assert not save.exists()


def test_the_word_rung_needs_nothing_loaded_and_carries_one_prompt():
    finder = sam3_words.load(None)
    assert finder.prompt == sam3_words.PROMPT
    assert sam3_words.PROMPT.strip() == sam3_words.PROMPT and sam3_words.PROMPT
    assert 0.0 < sam3_words.SURE_ENOUGH < 1.0


def test_the_table_says_which_rung_fits_something_and_which_does_not():
    fitting = [name for name, solution in train.SOLUTIONS.items() if solution.fits]
    assert len(fitting) == 1, "the keeper is the only thing fitted in this solution"
    assert len(train.SOLUTIONS) == 2, "two rungs, one generation apart"
    with pytest.raises(SystemExit):
        train.chosen("not-a-rung")


def test_the_borrowed_weights_are_two_generations_of_one_model_and_are_cached_here():
    assert weights.CACHE.parent == HERE
    assert weights.fitted("anything").parent == weights.CACHE
    # The tokenizer's tables come with the rung that is prompted with a word,
    # and with neither of the other kinds of file.
    assert set(weights.MODEL_FILES) < set(weights.WORD_FILES)
