"""The camera on the arm: what it is pointed at, and what it can and cannot see.

Two kinds of test, and the split is on purpose.

Most of it is geometry and needs no simulator at all, so it runs over a family
of hand poses and a family of drawn glasses rather than over one example. That
is where a rule that happens to work from one pose and fails from the next gets
caught.

The rest renders, and renders on **one table**, because a renderer is slow to
build and the machine is busy. Those tests are the ones that would otherwise be
silently wrong: that the rule about which glasses are in the picture agrees
with the picture itself, that the picture moves when the hand moves, and that a
look does not quietly re-measure the table.

No glass's size is written down here. The heights come from glasses drawn by
``family``, which is the project's rule.
"""

import math

import numpy as np
import pytest
from work_cell.glasses.shapes import KIND_RANGES, family
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.table.layout import TABLE_TOP_Z

from examiner.motion.push_motions import TRAVEL, Settings
from examiner.simulation import wrist_camera
from examiner.simulation.table_simulator import Simulator
from examiner.simulation.taken_from_problem_3 import TEST_SEEDS, TOP_VIEW_SIZE, Seen, Waypoint

# A spread of poses the hand can really stand in: over the glass zone, at both
# ends of the height band a waypoint is allowed, pointing every way.
HEADINGS = [math.radians(d) for d in (0, 37, 90, 143, 180, 221, 270, 314)]
PUSH_HEIGHT, TRAVEL_HEIGHT = Settings.default().push_height, TRAVEL
HEIGHTS = (PUSH_HEIGHT, (PUSH_HEIGHT + TRAVEL_HEIGHT) / 2, TRAVEL_HEIGHT)
POSES = [
    Waypoint(x, y, z, heading)
    for x, y in ((0.36, -0.40), (0.48, -0.26), (0.60, -0.12))
    for z in HEIGHTS
    for heading in HEADINGS
]


def drawn_glasses(each: int = 2, seed: int = 11) -> list:
    """A spread of drawn glasses, ``each`` of every kind the cell knows.

    Drawn, never written down. A stemmed glass and a tumbler stand differently
    in the frame and hide each other differently, so a rule about what is in
    the picture has to meet both.
    """
    return [outline for kind in KIND_RANGES for outline, _ in family(kind, each, seed=seed)]


def glass_heights(each: int = 2, seed: int = 11) -> list[float]:
    """How tall that spread of drawn glasses is."""
    return [outline.total_height for outline in drawn_glasses(each, seed)]


def reading(number: int, x: float, y: float, outline) -> Seen:
    """One glass's measurements, as a look would hand them over.

    The sizes are the drawn glass's own, without the examiner's noise on them,
    which keeps a test about what is hidden from also being a test about luck.
    """
    return Seen(
        id=number,
        x=x,
        y=y,
        height=outline.total_height,
        widest=outline.max_diameter,
        foot=2 * float(outline.radius[0]),
        standing=True,
    )


def lens_over(x: float, y: float, z: float, heading: float) -> Waypoint:
    """The hand pose whose camera stands over ``x, y``, turned to ``heading``.

    The arm's camera is mounted to one side of the hand, so a test that wants
    the lens in line with two glasses places the hand that far the other way.
    """
    left = (-math.sin(heading), math.cos(heading))
    return Waypoint(x - wrist_camera.SIDE * left[0], y - wrist_camera.SIDE * left[1], z, heading)


def ahead(hand: Waypoint, distance: float) -> tuple[float, float]:
    """The point on the table ``distance`` in front of the fingertips."""
    return hand.x + distance * math.cos(hand.heading), hand.y + distance * math.sin(hand.heading)


def glass_pixels(picture: np.ndarray) -> np.ndarray:
    """The glass pixels of a view: a glass's blue is above its red, the table's never is.

    Problem 3's straight-down view tests the same way. The one difference is
    that this camera can see past the edge of the table, and what is beyond it
    is black, which is why this asks for *above* rather than *at least*: black
    has its blue equal to its red.
    """
    return picture[:, :, 2].astype(int) > picture[:, :, 0].astype(int)


# --------------------------------------------------------------- the mounting


@pytest.mark.parametrize("hand", POSES)
def test_the_lens_sits_behind_the_fingertips_to_one_side_and_above_the_hand(hand):
    eye, forward = wrist_camera.camera_pose(hand)
    pointing = np.array([math.cos(hand.heading), math.sin(hand.heading), 0.0])
    left = np.array([-pointing[1], pointing[0], 0.0])
    fingertips = np.array([hand.x, hand.y, TABLE_TOP_Z + hand.z])
    assert eye[2] == pytest.approx(fingertips[2] + wrist_camera.UP)
    assert np.allclose(eye[:2], (fingertips - wrist_camera.BACK * pointing + wrist_camera.SIDE * left)[:2])
    # It looks at the table ahead of the fingertips, and the axis is a direction.
    assert np.linalg.norm(forward) == pytest.approx(1.0)
    assert forward[:2] @ pointing[:2] > 0
    assert forward[2] < 0


@pytest.mark.parametrize("hand", POSES)
def test_the_camera_is_above_the_table_everywhere_a_waypoint_may_go(hand):
    """The height band bounds the camera too, and the picture must land on the table from all of it."""
    eye, forward = wrist_camera.camera_pose(hand)
    assert eye[2] > TABLE_TOP_Z
    # Following the axis down to the table gets somewhere ahead of the lens.
    reach = (eye[2] - TABLE_TOP_Z) / -forward[2]
    middle = eye + reach * forward
    assert middle[2] == pytest.approx(TABLE_TOP_Z)
    assert (middle[:2] - eye[:2]) @ forward[:2] > 0


@pytest.mark.parametrize("hand", POSES)
def test_the_middle_pixel_is_where_the_axis_meets_the_table(hand):
    eye, forward = wrist_camera.camera_pose(hand)
    reach = (eye[2] - TABLE_TOP_Z) / -forward[2]
    middle = eye + reach * forward
    rows, columns = wrist_camera.WRIST_VIEW_SIZE
    row, column = wrist_camera.to_pixel(hand, middle[0], middle[1])
    assert row == pytest.approx(rows / 2 - 0.5)
    assert column == pytest.approx(columns / 2 - 0.5)


# ------------------------------------------------------ what counts as in the picture


@pytest.mark.parametrize("hand", POSES)
@pytest.mark.parametrize("distance", (0.10, 0.25))
def test_a_glass_in_front_of_the_jaw_is_seen_and_the_same_glass_behind_it_is_not(hand, distance):
    """The same glass, the same place, the hand turned round: in the picture, then out of it."""
    turned = Waypoint(hand.x, hand.y, hand.z, hand.heading + math.pi)
    for height in glass_heights():
        assert wrist_camera.sees(hand, *ahead(hand, distance), height)
        assert not wrist_camera.sees(turned, *ahead(hand, distance + wrist_camera.BACK), height)


@pytest.mark.parametrize("hand", POSES)
def test_a_glass_far_enough_to_the_side_is_not_seen(hand):
    """The picture has edges. A quarter turn off the heading is outside all of them."""
    beside = ahead(Waypoint(hand.x, hand.y, hand.z, hand.heading + math.pi / 2), 0.5)
    for height in glass_heights():
        assert not wrist_camera.sees(hand, *beside, height)


@pytest.mark.parametrize("hand", POSES[::4])
def test_a_glass_is_seen_when_any_of_it_is_in_the_picture_not_only_its_foot(hand):
    """A tall glass close to the hand has its foot below the frame and its body in it.

    This is the case the rule is written for, so the test insists it really
    happens rather than only that nothing breaks.
    """
    patch = [
        (hand.x + 0.02 * i, hand.y + 0.02 * j) for i in range(-25, 26) for j in range(-25, 26)
    ]
    for height in glass_heights():
        feet = {point for point in patch if wrist_camera.sees(hand, *point, 0.0)}
        whole = {point for point in patch if wrist_camera.sees(hand, *point, height)}
        # Standing a glass up can only bring it into the picture, never take it out.
        assert feet <= whole
    tallest = max(glass_heights())
    extra = [
        point
        for point in patch
        if wrist_camera.sees(hand, *point, tallest) and not wrist_camera.sees(hand, *point, 0.0)
    ]
    assert extra, "no glass anywhere is saved by its own height, so the rule is doing nothing"
    for point in extra:
        row, _ = wrist_camera.to_pixel(hand, *point)
        assert row > wrist_camera.WRIST_VIEW_SIZE[0] - 1, "its foot should be below the bottom of the frame"


@pytest.mark.parametrize("hand", POSES[::4])
def test_the_rule_and_the_projection_agree_about_the_edges_of_the_frame(hand):
    """``sees`` and ``to_pixel`` are two faces of one frustum and must not drift apart."""
    rows, columns = wrist_camera.WRIST_VIEW_SIZE
    eye, forward = wrist_camera.camera_pose(hand)
    for i in range(-20, 21):
        for j in range(-20, 21):
            x, y = hand.x + 0.03 * i, hand.y + 0.03 * j
            row, column = wrist_camera.to_pixel(hand, x, y)
            in_front = (np.array([x, y, TABLE_TOP_Z]) - eye) @ forward > 0
            on_film = in_front and -0.5 <= row <= rows - 0.5 and -0.5 <= column <= columns - 0.5
            assert wrist_camera.sees(hand, x, y, 0.0) == on_film, f"at ({x:.2f}, {y:.2f})"


# --------------------------------------------------- what hides what


def pair(kind: str, apart: float = 0.11, x: float = 0.42, y: float = -0.26) -> list[Seen]:
    """Two drawn glasses of one kind, one standing ``apart`` metres behind the other.

    The taller goes in front. A short glass in front of a tall one does not
    hide it, which is the whole reason this rule is worked out in the picture
    and not on a plan of the table, and it is tested on its own below.
    """
    near, far = sorted(family(kind, 2, seed=3), key=lambda drawn: -drawn[0].total_height)
    return [reading(0, x, y, near[0]), reading(1, x + apart, y, far[0])]


@pytest.mark.parametrize("hand", POSES)
def test_a_glass_with_the_table_to_itself_is_never_hidden(hand):
    for number, outline in enumerate(drawn_glasses()):
        alone = reading(number, *ahead(hand, 0.25), outline)
        assert wrist_camera.showing(hand, alone, [alone]) == 1.0


@pytest.mark.parametrize("kind", sorted(KIND_RANGES))
def test_a_glass_behind_a_glass_is_dropped_and_seeing_it_means_moving(kind):
    """The point of problem 4: the crowded glasses hide each other, so the arm must go round.

    Asked with the hand low, at the height it pushes at. The arm's camera rides well
    above the hand, so from higher up it can see over a near glass to one standing
    close behind it, and then nothing is hidden at all.
    """
    z = PUSH_HEIGHT
    glasses = pair(kind)
    in_line = lens_over(0.30, -0.26, z, 0.0)
    from_the_side = lens_over(0.475, -0.46, z, math.pi / 2)
    # Both are in frame from both poses, so it is being hidden and nothing else
    # that drops the far one.
    for hand in (in_line, from_the_side):
        assert all(wrist_camera.sees(hand, glass.x, glass.y, glass.height) for glass in glasses)
    assert [glass.id for glass in wrist_camera.in_picture(in_line, glasses)] == [0]
    assert wrist_camera.showing(in_line, glasses[1], glasses) < wrist_camera.SEEN_SHARE
    assert [glass.id for glass in wrist_camera.in_picture(from_the_side, glasses)] == [0, 1]
    assert wrist_camera.showing(from_the_side, glasses[1], glasses) == 1.0


@pytest.mark.parametrize("hand", POSES[::4])
def test_a_glass_in_front_can_only_hide_and_never_help(hand):
    """Adding a glass to the table never makes another glass easier to see."""
    glasses = [
        reading(number, *ahead(hand, 0.20 + 0.06 * number), outline)
        for number, outline in enumerate(drawn_glasses()[:5])
    ]
    for glass in glasses:
        shares = [wrist_camera.showing(hand, glass, glasses[:count]) for count in range(1, len(glasses) + 1)]
        for before, after in zip(shares, shares[1:], strict=False):
            assert after <= before + 1e-9
        assert 0.0 <= shares[-1] <= 1.0


@pytest.mark.parametrize("z", HEIGHTS)
def test_the_camera_looks_over_a_short_glass_but_not_through_a_tall_one(z):
    """Why the rule is worked out in the picture and not on a plan of the table.

    The lens rides above the rims, so a tall glass standing behind a short one
    still shows over it, while the same two glasses the other way round hide
    the short one completely. A rule that only asked which glass stands behind
    which would call both of these the same.
    """
    outlines = drawn_glasses()
    short = min(outlines, key=lambda outline: outline.total_height)
    tall = max(outlines, key=lambda outline: outline.total_height)
    hand = lens_over(0.30, -0.26, z, 0.0)
    short_first = [reading(0, 0.42, -0.26, short), reading(1, 0.53, -0.26, tall)]
    tall_first = [reading(0, 0.42, -0.26, tall), reading(1, 0.53, -0.26, short)]
    over = wrist_camera.showing(hand, short_first[1], short_first)
    through = wrist_camera.showing(hand, tall_first[1], tall_first)
    assert over > through + 0.25, "the tall glass behind should show over the short one in front"


def test_moving_the_jaw_changes_which_glasses_are_in_the_picture():
    """Looking from somewhere else is the only way to see somewhere else, and must show."""
    glasses = [
        reading(i, x, y, outline)
        for i, ((x, y), outline) in enumerate(
            zip(
                ((0.36, -0.40), (0.48, -0.26), (0.60, -0.12), (0.60, -0.40), (0.36, -0.12)),
                drawn_glasses()[:5],
                strict=True,
            )
        )
    ]
    near_side = lens_over(0.48, -0.46, PUSH_HEIGHT, math.pi / 2)
    far_side = lens_over(0.48, -0.06, PUSH_HEIGHT, -math.pi / 2)
    here = wrist_camera.in_picture(near_side, glasses)
    there = wrist_camera.in_picture(far_side, glasses)
    assert here and there
    assert {g.id for g in here} != {g.id for g in there}
    # Neither pose sees the whole table, which is the point of the problem.
    assert len(here) < len(glasses) and len(there) < len(glasses)


def test_the_readings_handed_back_are_the_readings_that_went_in():
    """Problem 4 narrows what a look returns. It must not re-measure or round anything."""
    # Spread across the frame rather than in a line, so that nothing is dropped
    # for standing behind anything: this test is about the readings themselves.
    glasses = [
        reading(i, 0.42 + 0.06 * i, -0.38 + 0.08 * i, outline)
        for i, outline in enumerate(drawn_glasses()[:4])
    ]
    kept = wrist_camera.in_picture(Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0), glasses)
    assert kept
    for glass in kept:
        assert any(glass is original for original in glasses)
    assert [g.id for g in kept] == sorted(g.id for g in kept)


# --------------------------------------------------------- the picture itself
#
# One table from here down. Building a renderer is slow and the machine is
# busy, so the examiner and the camera are made once and every test below shares
# them.


@pytest.fixture(scope="module")
def table():
    return Simulator(TEST_SEEDS)


@pytest.fixture(scope="module")
def camera(table):
    camera = wrist_camera.ArmCamera(table)
    yield camera
    camera.close()


def test_the_picture_is_the_shape_and_type_the_docstring_promises(table, camera):
    picture = camera.view(Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0))
    assert picture.shape == (*wrist_camera.WRIST_VIEW_SIZE, 3)
    assert picture.dtype == np.uint8
    assert picture.std() > 10.0, "a blank picture would pass every other test here"


def test_every_glass_the_rule_says_is_in_the_picture_really_is(table, camera):
    """The rule and the renderer are two separate pieces of geometry. They must agree."""
    hand = Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0)
    picture = camera.view(hand)
    glasses = glass_pixels(picture)
    inside = wrist_camera.in_picture(hand, table.look())
    assert len(inside) >= 3, "a look across the zone from travel height should catch most of the table"
    for glass in inside:
        row, column = wrist_camera.to_pixel(hand, glass.x, glass.y)
        patch = glasses[round(row) - 4 : round(row) + 5, round(column) - 4 : round(column) + 5]
        assert patch.any(), f"glass {glass.id} is not in the picture where to_pixel puts it"


def test_a_table_behind_the_jaw_is_in_no_picture_at_all(table, camera):
    """The far end of the table, looking away from every glass: no rule, no pixels."""
    hand = Waypoint(1.10, -0.26, TRAVEL_HEIGHT, 0.0)
    assert wrist_camera.in_picture(hand, table.look()) == ()
    assert not glass_pixels(camera.view(hand)).any()


def test_the_picture_follows_the_jaw(table, camera):
    """Same pose, same picture; different pose, different picture. Both matter."""
    hand = Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0)
    assert np.array_equal(camera.view(hand), camera.view(hand))
    turned = Waypoint(hand.x, hand.y, hand.z, hand.heading + math.pi / 4)
    lifted = Waypoint(hand.x, hand.y, PUSH_HEIGHT, hand.heading)
    assert not np.array_equal(camera.view(hand), camera.view(turned))
    assert not np.array_equal(camera.view(hand), camera.view(lifted))


def test_looking_through_the_camera_does_not_touch_the_table(table, camera):
    """A picture is not a measurement: it must not move a glass or spend a look's noise."""
    before = [table.position(i).copy() for i in range(len(table.glasses))]
    looks = table.looks
    camera.view(Waypoint(0.48, -0.26, TRAVEL_HEIGHT, math.pi / 2))
    wrist_camera.in_picture(Waypoint(0.48, -0.26, TRAVEL_HEIGHT, 0.0), table.look())
    assert table.looks == looks + 1, "in_picture must not take a look of its own"
    for i, was in enumerate(before):
        assert np.allclose(table.position(i), was)


@pytest.fixture(scope="module")
def in_line():
    """A second table, two glasses deep: the taller in front, the other hiding behind it.

    The only table here that is built rather than drawn, because what is being
    checked is one glass standing behind another and a drawn table does not
    promise to hold such a pair.
    """
    glasses = [
        SpawnedGlass(f"glass_{number}", "straight_glass", outline, (x, -0.26, TABLE_TOP_Z), 0.0)
        for number, (outline, x) in enumerate(
            zip(
                sorted((drawn[0] for drawn in family("straight_glass", 2, seed=3)),
                       key=lambda outline: -outline.total_height),
                (0.42, 0.53),
                strict=True,
            )
        )
    ]
    simulator = Simulator(0, glasses)
    camera = wrist_camera.ArmCamera(simulator)
    yield simulator, camera
    camera.close()


def test_the_rule_and_the_renderer_agree_about_what_hides_what(in_line):
    """``showing`` works the hiding out from four measured numbers a glass. This is the truth.

    ``labels`` asks the renderer which glass each pixel belongs to, so the
    share of a glass that is really left showing can be counted rather than
    argued about. The rule is a box standing in for a glass, so it is held to
    being close rather than exact.
    """
    simulator, camera = in_line
    glasses = simulator.look()
    behind = glasses[1]
    # Low, for the reason the geometric test of the same thing gives.
    straight_at = lens_over(0.30, -0.26, PUSH_HEIGHT, 0.0)
    from_the_side = lens_over(0.475, -0.46, PUSH_HEIGHT, math.pi / 2)
    clear = int((camera.labels(from_the_side) == behind.id).sum())
    hidden = int((camera.labels(straight_at) == behind.id).sum())
    assert clear > 1000, "from the side the far glass should be whole in the picture"
    # What the renderer really left of it, against what the rule predicted.
    assert hidden < clear / 2
    assert wrist_camera.showing(straight_at, behind, glasses) == pytest.approx(hidden / clear, abs=0.2)
    assert wrist_camera.showing(from_the_side, behind, glasses) == 1.0
    # And the rule's answer is the one the look acts on.
    assert [glass.id for glass in wrist_camera.in_picture(straight_at, glasses)] == [0]
    assert [glass.id for glass in wrist_camera.in_picture(from_the_side, glasses)] == [0, 1]


def test_a_glass_the_rule_keeps_has_pixels_and_one_it_drops_has_few(table, camera):
    """On a drawn table, every reading handed over belongs to a glass the picture really shows."""
    hand = Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0)
    marks = camera.labels(hand)
    kept = {glass.id for glass in wrist_camera.in_picture(hand, table.look())}
    assert kept, "nothing at all was seen, so this test is checking nothing"
    for glass in table.look():
        pixels = int((marks == glass.id).sum())
        if glass.id in kept:
            assert pixels > 100, f"glass {glass.id} was handed over but is not in the picture"
        elif wrist_camera.sees(hand, glass.x, glass.y, glass.height):
            # Dropped for being hidden, not for being out of frame: it may still
            # show an edge, but it cannot be one of the plainest glasses there.
            assert pixels < max(
                int((marks == other).sum()) for other in kept
            ), f"glass {glass.id} was dropped but shows more than a glass that was kept"


def test_the_world_has_no_fixed_camera_and_the_picture_keeps_problem_threes_shape(table, camera):
    """The arm's camera is the only camera, and a look does not change the world it renders."""
    import mujoco

    # Problem 3 writes an overhead camera into its world. Problem 4's world is
    # the common one, which has none: the only camera is the one the arm carries.
    assert table.model.ncam == 0
    # The same shaped array as problem 3's overhead picture, so a policy fitted
    # there can be shown one of these.
    assert wrist_camera.WRIST_VIEW_SIZE == TOP_VIEW_SIZE
    was = table.model.vis.global_.fovy
    hand = Waypoint(0.30, -0.26, TRAVEL_HEIGHT, 0.0)
    assert camera.view(hand).shape == (*TOP_VIEW_SIZE, 3)
    assert table.model.vis.global_.fovy == was, "a look must leave the model as it found it"
    assert mujoco.mj_name2id(table.model, mujoco.mjtObj.mjOBJ_CAMERA, "top") == -1
