import numpy as np
import pytest
from work_cell.glasses.detect import (
    Detection,
    classify,
    find_glasses,
    foot_of,
    merge_sightings,
    standing_on_the_table,
    the_one_in_the_middle,
    where_they_stand,
)
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.shapes import family, short_stemmed, stemmed, straight, tapered


def profile_of(outline):
    return profile_from_outline(outline)


# ------------------------------------------------------------- the mask


class _Lens:
    """The intrinsics of a plain 320x240 camera, for the tests below."""

    fx = fy = 277.19
    cx, cy = 160.0, 120.0


def _looking_straight_down(height: float) -> np.ndarray:
    """A camera ``height`` above the world origin, pointing at the floor.

    Camera axes are x right, y down, z forwards, so pointing z downwards means
    the camera's y runs along world -y and its x along world x.
    """
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, -1.0, 0.0, 0.0],
            [0.0, 0.0, -1.0, height],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )


def test_something_standing_on_the_table_is_found():
    table_z, camera_z = 0.75, 1.20
    depth = np.full((40, 40), camera_z - table_z)  # the bare table
    depth[15:25, 15:25] = camera_z - table_z - 0.15  # a 150 mm glass on it

    mask = standing_on_the_table(depth, _Lens(), _looking_straight_down(camera_z), table_z)
    assert mask[20, 20], "the glass should be found"
    assert not mask[2, 2], "the table itself should not"


def test_the_table_itself_is_never_a_glass():
    table_z, camera_z = 0.75, 1.20
    depth = np.full((30, 30), camera_z - table_z)
    assert not standing_on_the_table(depth, _Lens(), _looking_straight_down(camera_z), table_z).any()


def test_a_pixel_with_no_distance_cannot_be_placed_and_is_dropped():
    """Sky, and anything past the camera's range, comes back empty."""
    table_z, camera_z = 0.75, 1.20
    depth = np.full((20, 20), np.nan)
    assert not standing_on_the_table(depth, _Lens(), _looking_straight_down(camera_z), table_z).any()

    depth = np.zeros((20, 20))  # zero is how "no reading" is reported too
    assert not standing_on_the_table(depth, _Lens(), _looking_straight_down(camera_z), table_z).any()


def test_something_lying_flat_on_the_table_is_not_standing_on_it():
    """The rack's marker is printed flat on its base, and must not read as a glass."""
    table_z, camera_z = 0.75, 1.20
    depth = np.full((30, 30), camera_z - table_z)
    depth[10:20, 10:20] = camera_z - table_z - 0.001  # a millimetre proud
    assert not standing_on_the_table(depth, _Lens(), _looking_straight_down(camera_z), table_z).any()


def test_a_depth_picture_has_to_be_a_picture():
    with pytest.raises(ValueError):
        standing_on_the_table(np.zeros((4, 4, 3)), _Lens(), np.eye(4), 0.75)


# --------------------------------------------------------- finding blobs


def test_two_separate_blobs_are_two_glasses():
    mask = np.zeros((60, 60), dtype=bool)
    mask[5:25, 5:25] = True
    mask[35:55, 35:55] = True
    found = find_glasses(mask, lambda c, r, z: (c / 100, r / 100, z), table_z=0.75, min_pixels=50)
    assert len(found) == 2


def test_a_speck_is_not_a_glass():
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:13, 10:13] = True
    assert find_glasses(mask, lambda c, r, z: (c, r, z), table_z=0.75, min_pixels=50) == []


def test_a_detection_lands_where_the_blob_is():
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    found = find_glasses(mask, lambda c, r, z: (c, r, z), table_z=0.75, min_pixels=50)
    assert found[0].position[0] == pytest.approx(29.5)
    assert found[0].position[2] == pytest.approx(0.75)


def test_the_footprint_is_measured_on_the_table_not_in_pixels():
    """A blob 20 pixels across, at a hundred pixels to the metre, is 200 mm.

    The width has to come out of the projection, because the same blob seen
    from twice as high covers half as many pixels and is still the same glass.
    """
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    found = find_glasses(mask, lambda c, r, z: (c / 100, r / 100, z), table_z=0.75, min_pixels=50)
    assert found[0].rough_width == pytest.approx(0.20, abs=0.005)


# ------------------------------------------------------- deciding the kind


def test_a_tube_is_a_straight_glass():
    assert classify(profile_of(straight(height=0.090, rim_diameter=0.080))) == "straight_glass"


def test_a_cone_is_a_tapered_glass():
    assert classify(profile_of(tapered(height=0.175, rim_diameter=0.090))) == "tapered_glass"


def test_a_bowl_on_a_long_stem_is_a_stemmed_glass():
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)
    assert classify(profile_of(outline)) == "stemmed_glass"


def test_a_bowl_on_a_short_stem_is_a_short_stemmed_glass():
    outline = short_stemmed(height=0.150, bowl_diameter=0.070, stem_diameter=0.015)
    assert classify(profile_of(outline)) == "short_stemmed_glass"


def test_a_stemmed_glass_is_not_mistaken_for_a_tapered_one():
    # Its bowl slopes, so the order the tests are applied in matters: look for
    # a stem before asking whether the wall leans.
    for outline, _ in family("stemmed_glass", 20, seed=8):
        assert classify(profile_of(outline)) in {"stemmed_glass", "short_stemmed_glass"}


@pytest.mark.parametrize(
    "kind_name", ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]
)
def test_every_drawn_glass_gets_a_kind_whose_rule_can_hold_it(kind_name):
    """What the classifier owes the arm is a workable grip, not a matching label.

    It is tempting to require that a glass drawn as tapered comes back as
    tapered. That is the wrong test. A shallow cone has a wall upright enough
    for flat pads, so calling it straight is not a mistake — the straight rule
    grips it perfectly well, and insisting on the label would be testing how
    the glass was generated rather than whether the arm can pick it up.

    So the requirement is the one that matters: whatever kind the profile is
    given, that kind's rule must find somewhere safe to hold it.
    """
    from work_cell.glasses import spec
    from work_cell.glasses.rules import NoGrip, find_grip

    failures = []
    for outline, props in family(kind_name, 40, seed=9):
        profile = profile_of(outline)
        got = classify(profile)
        if got is None:
            failures.append(("no kind", props))
            continue
        try:
            find_grip(profile, spec.kind(got), gripper_max_opening=0.095)
        except NoGrip as why:
            failures.append((f"{got}: {why}", {k: round(v, 4) for k, v in props.items()}))
    assert not failures, f"{len(failures)} of 40 failed, first: {failures[:1]}"


def test_a_clear_cut_shape_gets_the_label_you_would_expect():
    # Where the shape is unambiguous, the classifier should agree with a person.
    assert classify(profile_of(straight(height=0.090, rim_diameter=0.080, taper=0.02))) == (
        "straight_glass"
    )
    assert classify(profile_of(tapered(height=0.140, rim_diameter=0.100, base_fraction=0.40))) == (
        "tapered_glass"
    )


def test_a_shape_no_rule_describes_is_refused_rather_than_forced():
    # A flat disc: no stem, and not tall enough to ask about its wall.
    from work_cell.glasses.profile import Profile

    flat = Profile(np.array([0.0, 0.001, 0.002]), np.array([0.08, 0.08, 0.08]))
    assert classify(flat) is None


# --- two views from above ------------------------------------------------

# The tallest glass this cell handles. A limit of the cell, not the size of any
# glass: it is what tells a pair of sightings of one glass from a pair of
# sightings of two different ones.
TALLEST = 0.26


def _laid_on_the_table(true_xy, height, width, camera_xy, camera_height, name="glass_0"):
    """What one picture from above reports for a glass it cannot range on.

    The camera lays the glass's widest part down on the table, which pushes it
    away from the point under the camera. This is that, and nothing else.
    """
    stretch = camera_height / (camera_height - height)
    here = np.asarray(camera_xy, float)
    seen = here + stretch * (np.asarray(true_xy, float) - here)
    return Detection(
        name=name,
        position=np.array([seen[0], seen[1], 0.75]),
        rough_width=width * stretch,
    )


def test_two_views_put_a_glass_back_where_it_really_stands():
    camera_height, baseline = 0.45, 0.12
    truth, height, width = np.array([0.62, -0.21]), 0.19, 0.082
    first_camera = np.array([0.54, -0.09 - baseline / 2])
    second_camera = np.array([0.54, -0.09 + baseline / 2])

    found = where_they_stand(
        [_laid_on_the_table(truth, height, width, first_camera, camera_height)],
        first_camera,
        [_laid_on_the_table(truth, height, width, second_camera, camera_height)],
        second_camera,
        camera_height,
        tallest=TALLEST,
    )

    assert len(found) == 1
    assert np.allclose(found[0].position[:2], truth, atol=1e-6)
    assert found[0].rough_width == pytest.approx(width, abs=1e-6)


def test_it_works_across_a_family_of_glasses_not_one_example():
    """A correction that only works at one height is not a correction."""
    camera_height, baseline = 0.45, 0.12
    first_camera = np.array([0.54, -0.09 - baseline / 2])
    second_camera = np.array([0.54, -0.09 + baseline / 2])

    rng = np.random.default_rng(4)
    for _ in range(40):
        truth = np.array([rng.uniform(0.36, 0.72), rng.uniform(-0.32, 0.14)])
        height = float(rng.uniform(0.05, TALLEST))
        width = float(rng.uniform(0.04, 0.12))

        found = where_they_stand(
            [_laid_on_the_table(truth, height, width, first_camera, camera_height)],
            first_camera,
            [_laid_on_the_table(truth, height, width, second_camera, camera_height)],
            second_camera,
            camera_height,
            tallest=TALLEST,
        )
        assert len(found) == 1, f"lost a glass {height * 1000:.0f} mm tall"
        assert np.allclose(found[0].position[:2], truth, atol=1e-6)
        assert found[0].rough_width == pytest.approx(width, abs=1e-6)


def test_a_flat_thing_on_the_table_is_left_where_it_was():
    """Zero height means no correction: the marker on the rack is exactly this."""
    camera_height = 0.45
    truth = np.array([0.5, 0.1])
    first_camera = np.array([0.54, -0.15])
    second_camera = np.array([0.54, -0.03])

    found = where_they_stand(
        [_laid_on_the_table(truth, 0.0, 0.05, first_camera, camera_height)],
        first_camera,
        [_laid_on_the_table(truth, 0.0, 0.05, second_camera, camera_height)],
        second_camera,
        camera_height,
        tallest=TALLEST,
    )
    assert np.allclose(found[0].position[:2], truth, atol=1e-9)


def test_a_glass_only_one_picture_caught_is_left_out():
    """Its height cannot be measured, so where it stands is not known."""
    camera_height = 0.45
    first_camera, second_camera = np.array([0.54, -0.15]), np.array([0.54, -0.03])
    seen = _laid_on_the_table(np.array([0.62, -0.21]), 0.19, 0.082, first_camera, camera_height)
    assert where_they_stand([seen], first_camera, [], second_camera, camera_height, tallest=TALLEST) == []


def test_two_glasses_are_not_mixed_up_with_each_other():
    camera_height, baseline = 0.45, 0.12
    first_camera = np.array([0.54, -0.09 - baseline / 2])
    second_camera = np.array([0.54, -0.09 + baseline / 2])
    both = [(np.array([0.45, -0.25]), 0.09, 0.07), (np.array([0.66, 0.05]), 0.24, 0.10)]

    found = where_they_stand(
        [
            _laid_on_the_table(xy, h, w, first_camera, camera_height, f"glass_{i}")
            for i, (xy, h, w) in enumerate(both)
        ],
        first_camera,
        [
            _laid_on_the_table(xy, h, w, second_camera, camera_height, f"glass_{i}")
            for i, (xy, h, w) in enumerate(both)
        ],
        second_camera,
        camera_height,
        tallest=TALLEST,
    )
    assert len(found) == 2
    placed = sorted(found, key=lambda d: d.position[0])
    for got, (xy, _, width) in zip(placed, both, strict=True):
        assert np.allclose(got.position[:2], xy, atol=1e-6)
        assert got.rough_width == pytest.approx(width, abs=1e-6)


def test_overlapping_stations_report_each_glass_once():
    here = Detection(name="glass_0", position=np.array([0.5, 0.1, 0.75]), rough_width=0.08)
    again = Detection(name="glass_1", position=np.array([0.507, 0.103, 0.75]), rough_width=0.081)
    apart = Detection(name="glass_2", position=np.array([0.66, -0.2, 0.75]), rough_width=0.07)

    merged = merge_sightings([here, again, apart])
    assert len(merged) == 2
    assert [d.name for d in merged] == ["glass_0", "glass_1"]


def test_only_the_glass_in_the_middle_is_measured():
    """A side-on picture catches the neighbours too, and measured together
    they make one glass as tall as the picture."""
    mask = np.zeros((40, 60), dtype=bool)
    mask[5:35, 26:34] = True   # the one being looked at, across the middle
    mask[0:40, 2:8] = True     # a taller neighbour off to the left
    mask[10:20, 52:58] = True  # and another to the right

    only = the_one_in_the_middle(mask)
    assert only[5:35, 26:34].all()
    assert not only[:, :20].any()
    assert not only[:, 40:].any()


def test_the_middle_one_is_kept_even_when_it_is_not_the_biggest():
    mask = np.zeros((40, 60), dtype=bool)
    mask[18:22, 28:32] = True  # small, in the middle
    mask[0:40, 0:10] = True    # big, off to one side
    only = the_one_in_the_middle(mask)
    assert only[18:22, 28:32].all()
    assert not only[:, 0:10].any()


def test_an_empty_picture_is_handed_back_unchanged():
    mask = np.zeros((10, 10), dtype=bool)
    assert not the_one_in_the_middle(mask).any()


def test_two_glasses_are_not_read_as_one_glass_somewhere_else():
    """The failure this pair of pictures is most prone to.

    Pairing a sighting of one glass with a sighting of a *different* one gives
    an apparent movement that is still parallel to the baseline, so long as the
    two stand apart along it — and parallel is all the arithmetic asks for.
    The pair then reports a glass at a place where nothing is standing, which
    is how the arm ends up reaching into thin air or into its neighbour.

    What rules it out is the height such a pair implies, which is taller than
    any glass the cell handles.
    """
    camera_height, baseline = 0.45, 0.12
    first_camera = np.array([0.47, -0.29 - baseline / 2])
    second_camera = np.array([0.47, -0.29 + baseline / 2])

    # Two glasses a slot apart along the baseline, which is the awkward case.
    left = np.array([0.47, -0.40])
    right = np.array([0.47, -0.18])
    first = [
        _laid_on_the_table(left, 0.12, 0.07, first_camera, camera_height, "a"),
        _laid_on_the_table(right, 0.12, 0.07, first_camera, camera_height, "b"),
    ]
    second = [
        _laid_on_the_table(left, 0.12, 0.07, second_camera, camera_height, "a"),
        _laid_on_the_table(right, 0.12, 0.07, second_camera, camera_height, "b"),
    ]

    found = where_they_stand(
        first, first_camera, second, second_camera, camera_height, tallest=TALLEST
    )
    assert len(found) == 2
    for glass in found:
        nearest = min(np.linalg.norm(glass.position[:2] - real) for real in (left, right))
        assert nearest < 0.01, "reported a glass where none is standing"


def test_a_pair_implying_an_impossible_glass_is_refused():
    camera_height = 0.45
    first_camera = np.array([0.47, -0.35])
    second_camera = np.array([0.47, -0.23])
    # Drawn as a glass far taller than the cell handles, so the pair cannot be
    # two sightings of one glass the arm could ever be asked to pick up.
    truth = np.array([0.50, -0.30])
    first = [_laid_on_the_table(truth, 0.40, 0.07, first_camera, camera_height)]
    second = [_laid_on_the_table(truth, 0.40, 0.07, second_camera, camera_height)]
    assert (
        where_they_stand(first, first_camera, second, second_camera, camera_height, tallest=TALLEST)
        == []
    )


def test_the_camera_has_to_be_above_the_tallest_glass():
    with pytest.raises(ValueError, match="above the tallest"):
        where_they_stand([], np.array([0.4, -0.3]), [], np.array([0.4, -0.2]), 0.20, tallest=0.26)


# --- the foot, seen at a slant ---------------------------------------------


def _side_on_camera(height=0.120, fx=277.2, size=(240, 320)):
    """A camera that many metres of this project assume: level, looking along
    +x, that many metres above the table. Returns its to_world and a projector."""
    rows, columns = size
    cx, cy = columns / 2.0, rows / 2.0
    eye = np.array([0.0, 0.0, height])
    # Image right is -y in the room, image down is -z: the usual optical frame.
    rotation = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])

    def to_world(column, row, z):
        direction = np.array([(column - cx) / fx, (row - cy) / fx, 1.0])
        ray = rotation @ direction
        return eye + ray * ((z - eye[2]) / ray[2])

    def to_pixel(point):
        relative = np.asarray(point, float) - eye
        camera = rotation.T @ relative
        return (cx + fx * camera[0] / camera[2], cy + fx * camera[1] / camera[2])

    return to_world, to_pixel, size


def _disc_mask(centre, radius, to_pixel, size):
    """The silhouette of a disc lying flat on the table."""
    mask = np.zeros(size, dtype=bool)
    angles = np.linspace(0.0, 2.0 * np.pi, 400, endpoint=False)
    by_row: dict[int, list[float]] = {}
    for angle in angles:
        point = (centre[0] + radius * np.cos(angle), centre[1] + radius * np.sin(angle), 0.0)
        column, row = to_pixel(point)
        by_row.setdefault(int(round(row)), []).append(column)
    for row, columns in by_row.items():
        if 0 <= row < size[0]:
            left, right = int(round(min(columns))), int(round(max(columns)))
            mask[row, max(left, 0) : min(right, size[1] - 1) + 1] = True
    return mask


def test_the_foot_is_found_at_its_middle_not_at_its_near_rim():
    """A foot is a disc seen at a slant, so its outline is an ellipse.

    Taking the middle column at the lowest row mixes two different points: the
    lowest row is the rim nearest the camera. It lands one foot-radius short,
    towards the camera, every single time — which is exactly the kind of error
    that never looks like an error, because it is the same on every glass.
    """
    to_world, to_pixel, size = _side_on_camera()
    for distance in (0.34, 0.38, 0.45):
        for sideways in (-0.05, 0.0, 0.07):
            for radius in (0.026, 0.040):
                centre = np.array([distance, sideways])
                mask = _disc_mask(centre, radius, to_pixel, size)
                found = foot_of(mask, to_world, table_z=0.0)
                assert found is not None
                off = float(np.linalg.norm(found[:2] - centre))
                assert off < 0.004, (
                    f"foot found {off * 1000:.1f} mm from the middle of a disc "
                    f"{radius * 2000:.0f} mm across at {distance * 1000:.0f} mm"
                )


def test_the_foot_does_not_land_on_the_rim_nearest_the_camera():
    # The specific wrong answer, named so it cannot come back quietly.
    to_world, to_pixel, size = _side_on_camera()
    centre, radius = np.array([0.38, 0.0]), 0.026
    found = foot_of(_disc_mask(centre, radius, to_pixel, size), to_world, table_z=0.0)
    near_rim = np.array([centre[0] - radius, centre[1]])
    assert np.linalg.norm(found[:2] - centre) < np.linalg.norm(found[:2] - near_rim)


def test_a_short_glass_is_not_thrown_out_for_looking_flat():
    """A glass with almost no lean to measure reads as shrink just over 1 as
    often as just under it, and half of those were being refused."""
    camera_height, baseline = 0.434, 0.118
    first_camera = np.array([0.469, -0.408])
    second_camera = np.array([0.469, -0.408 + baseline])
    truth = np.array([0.315, -0.457])

    # The sighting from one camera is out by a few millimetres, which for a
    # glass this short is bigger than the lean being measured.
    one = _laid_on_the_table(truth, 0.098, 0.062, first_camera, camera_height)
    other = _laid_on_the_table(truth, 0.098, 0.062, second_camera, camera_height)
    other = Detection(
        name=other.name,
        position=other.position + np.array([0.006, 0.0, 0.0]),
        rough_width=other.rough_width,
    )

    found = where_they_stand(
        [one], first_camera, [other], second_camera, camera_height, tallest=0.26
    )
    assert found, "a short glass must survive the error in finding its middle"
    assert float(np.linalg.norm(found[0].position[:2] - truth)) < 0.02


def test_a_pair_that_cannot_be_the_same_glass_is_still_refused():
    """The forgiveness above must not become a free pass."""
    camera_height = 0.434
    first_camera = np.array([0.469, -0.408])
    second_camera = np.array([0.469, -0.290])
    one = _laid_on_the_table(np.array([0.315, -0.457]), 0.098, 0.062, first_camera, camera_height)
    far = _laid_on_the_table(np.array([0.60, -0.10]), 0.098, 0.062, second_camera, camera_height)
    assert where_they_stand(
        [one], first_camera, [far], second_camera, camera_height, tallest=0.26
    ) == []
