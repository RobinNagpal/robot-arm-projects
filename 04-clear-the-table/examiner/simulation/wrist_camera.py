"""The camera on the arm's wrist, and what it can see from where the hand is.

Problem 3 had a camera fixed above the table, which saw the whole table every time. Problem
4 has no such camera. The camera rides on the arm's wrist, so it sees only the patch of
table the hand is turned towards, and a solution that wants to see the far corner has to
take the arm there and pay for the trip in arm time. That is what a real cell is like.

**Where the camera is mounted.** On the real UR5e, the spot straight above the hand is
where the wrist is, and the hand points along the line a camera there would look down, so
the arm and the hand would fill the middle of the picture. So the camera sits to one side
of the hand and a little above it, and is turned to look at the patch of table ahead of the
fingertips. The hand is then at the edge of the picture and not in the way.

**Glasses hide each other, and that is why one look is not enough.** A glass standing
behind a nearer glass is not in the picture, and a solution cannot tell that it is missing,
because a hidden glass is simply not there. The glasses that hide each other most are the
crowded ones, which are exactly the ones a solution has come to separate, so it has to look
from more than one place.

Three things come out of this module. ``WristCameraRenderer.render_picture()`` renders the picture.
``glasses_the_camera_can_see()`` says which glasses the camera can really see, which is what the box model
is trained to find. ``WristCameraRenderer.glass_index_per_pixel()`` asks the renderer which glass each
pixel belongs
to, and is for the tests, which hold the rule about what hides what to the picture.

A pose here is a ``Waypoint``: the fingertips' place, with ``z`` measured from the table
top, and the way the hand points. Nothing here moves the table or the arm; a look is a
question about a pose, and the pose comes from the caller.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable

import mujoco
import numpy as np
from work_cell.table.layout import TABLE_TOP_Z

from examiner.simulation.table_simulator import TableSimulator
from examiner.simulation.taken_from_problem_3 import TOP_VIEW_FOVY_DEG, TOP_VIEW_SIZE, Seen, Waypoint

# ------------------------------------------------------------------ the mounting
#
# Where the lens is, measured from the fingertips along the way the hand points.
LENS_BEHIND_FINGERTIPS = 0.10  # behind the fingertips
LENS_ABOVE_HAND = 0.22  # above the middle of the hand
LENS_LEFT_OF_PUSH = 0.12  # to the left of the pushing direction
LENS_LOOKS_THIS_FAR_AHEAD = 0.25  # the camera looks at the table this far ahead of the fingertips

# The picture is the size and the angle of problem 3's straight-down view, on
# purpose. A learned model built for problem 3's pictures meets the same shaped
# array here, and from the viewing places the glasses are about the size it saw
# them before. It is deliberately not a new number invented for this problem.
WRIST_VIEW_SIZE = TOP_VIEW_SIZE
WRIST_VIEW_FOVY_DEG = TOP_VIEW_FOVY_DEG

# ---------------------------------------------------------------- what counts as seen
#
# How much of a glass must be showing in the picture, as a share of the whole
# of it, for the look to hand its reading over. Half.
#
# A glass behind another glass is the case this is for, and it is deliberately
# not all-or-nothing: a glass with two thirds of itself showing is read as
# usual, and one peeping out by a third is not read at all. Half is where the
# line falls because of what a reading **is**. ``Seen`` carries the glass's
# middle and its width, and both are measured off the silhouette the camera
# sees; a neighbour hides a glass from one side and not from both, so once more
# than half of it is covered its own middle is behind the neighbour and the
# reading would be of a place the camera cannot see. The noise the examiner puts
# on a reading is problem 2's, measured on glasses in full view, and handing
# that out for a glass that is mostly hidden would claim an accuracy nobody
# measured.
#
# A solution that wants the glass behind the glass has to move the arm and
# look from somewhere else. That is the cost this problem exists to measure.
LEAST_VISIBLE_SHARE = 0.5


def lens_position_and_direction(hand: Waypoint) -> tuple[np.ndarray, np.ndarray]:
    """Where the lens is in the world, and a unit vector along the way it points."""
    ahead = np.array([math.cos(hand.heading), math.sin(hand.heading), 0.0])
    left = np.array([-ahead[1], ahead[0], 0.0])
    tip = np.array([hand.x, hand.y, TABLE_TOP_Z + hand.z])
    eye = (
        tip
        - LENS_BEHIND_FINGERTIPS * ahead
        + LENS_LEFT_OF_PUSH * left
        + np.array([0.0, 0.0, LENS_ABOVE_HAND])
    )
    aim = np.array([hand.x, hand.y, TABLE_TOP_Z]) + LENS_LOOKS_THIS_FAR_AHEAD * ahead
    forward = aim - eye
    return eye, forward / np.linalg.norm(forward)


def _lens_axes(hand: Waypoint) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The eye and the camera's three axes: forward, right in the picture, up in the picture.

    The camera does not roll — its up stays as near the world's up as it can —
    because the arm only ever turns the hand about the vertical.
    """
    eye, forward = lens_position_and_direction(hand)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    return eye, forward, right, np.cross(right, forward)


class WristCameraRenderer:
    """The camera on one table's arm. Building it is slow; keep it.

    A renderer holds a graphics context, so make one per table and call
    ``render_picture()`` as often as the solution looks. The camera itself is moved on
    every call, which is the whole point of it.
    """

    def __init__(self, simulator: TableSimulator) -> None:
        self.simulator = simulator
        self.renderer = mujoco.Renderer(simulator.model, *WRIST_VIEW_SIZE)
        # A free camera is not in the world at all: it is placed on every call,
        # so it can follow the hand without the world being built again.
        self.free_camera = mujoco.MjvCamera()
        self.free_camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        # Which glass each geom of the world belongs to, for ``glass_index_per_pixel``. The
        # table, the arm and the sky are all -1.
        self.glass_of_geom = np.full(simulator.model.ngeom, -1, dtype=int)
        for glass, body in enumerate(simulator.bodies):
            self.glass_of_geom[simulator.model.geom_bodyid == body] = glass

    def render_picture(self, hand: Waypoint) -> np.ndarray:
        """The table from the hand's pose, right now: ``WRIST_VIEW_SIZE + (3,)``, ``uint8``, RGB."""
        started = time.perf_counter()
        self._aim_at_the_lens(hand)
        # MuJoCo keeps a free camera's angle of view in the model and nowhere
        # else, so it is set for this render and put back. The films render
        # with the same model and would otherwise be reframed by a look.
        model = self.simulator.model
        was = model.vis.global_.fovy
        model.vis.global_.fovy = WRIST_VIEW_FOVY_DEG
        try:
            self.renderer.update_scene(self.simulator.data, self.free_camera)
            picture = self.renderer.render().copy()
        finally:
            model.vis.global_.fovy = was
        # Rendering is the examiner's cost, not the solution's thinking time.
        self.simulator.seconds += time.perf_counter() - started
        return picture

    def glass_index_per_pixel(self, hand: Waypoint) -> np.ndarray:
        """Which glass each pixel of that same picture belongs to, or -1 for anything else.

        **This is not something a solution is given.** A real camera has no
        such picture and the contract has nowhere to put one. It is here
        because ``unhidden_share`` works out what hides what from a few measured
        numbers, and this is the renderer's own answer to the same question,
        which is what the tests hold the rule against.
        """
        started = time.perf_counter()
        self._aim_at_the_lens(hand)
        model = self.simulator.model
        was = model.vis.global_.fovy
        model.vis.global_.fovy = WRIST_VIEW_FOVY_DEG
        try:
            self.renderer.enable_segmentation_rendering()
            self.renderer.update_scene(self.simulator.data, self.free_camera)
            # Two planes: what the pixel is, and which one of them it is.
            segments = self.renderer.render()
        finally:
            self.renderer.disable_segmentation_rendering()
            model.vis.global_.fovy = was
        labelled = np.full(segments.shape[:2], -1, dtype=int)
        geoms = segments[:, :, 1] == mujoco.mjtObj.mjOBJ_GEOM
        labelled[geoms] = self.glass_of_geom[segments[:, :, 0][geoms]]
        self.simulator.seconds += time.perf_counter() - started
        return labelled

    def _aim_at_the_lens(self, hand: Waypoint) -> None:
        """Put the free camera where the hand's pose says the lens is."""
        eye, forward = lens_position_and_direction(hand)
        if eye[2] <= TABLE_TOP_Z:
            raise ValueError(f"the camera is {1000 * (TABLE_TOP_Z - eye[2]):.0f} mm below the table top")
        # A free camera is described by the point it looks at and how far away
        # it is, so a point one metre along the axis is used.
        self.free_camera.lookat[:] = eye + forward
        self.free_camera.distance = 1.0
        self.free_camera.azimuth = math.degrees(math.atan2(forward[1], forward[0]))
        self.free_camera.elevation = math.degrees(math.asin(forward[2]))

    def close(self) -> None:
        self.renderer.close()


def table_point_to_pixel(hand: Waypoint, x: float, y: float, z: float = 0.0) -> tuple[float, float]:
    """Where a point in the world falls in the picture: (row, column), fractional.

    ``x`` and ``y`` are metres on the table and ``z`` is height above the table
    top, as a waypoint's is. Outside 0..383 for a point outside the frame, and
    meaningless for a point behind the lens, which ``in_camera_frame`` is for.
    """
    eye, forward, right, up = _lens_axes(hand)
    rows, columns = WRIST_VIEW_SIZE
    towards = np.array([x, y, TABLE_TOP_Z + z]) - eye
    # How far across and up the point is, as a fraction of the half frame at
    # its own depth. The frame is square, so one angle serves both directions.
    half = float(towards @ forward) * math.tan(math.radians(WRIST_VIEW_FOVY_DEG) / 2)
    across = float(towards @ right) / half
    upward = float(towards @ up) / half
    return (1.0 - upward) / 2.0 * rows - 0.5, (1.0 + across) / 2.0 * columns - 0.5


def in_camera_frame(hand: Waypoint, x: float, y: float, height: float = 0.0) -> bool:
    """Is a glass standing at ``x, y`` and ``height`` tall inside the picture?

    The glass is treated as the upright line from its foot on the table top to
    the middle of its rim, and it counts as seen when any part of that line is
    inside the camera's frustum. The line and not the foot alone, because a
    glass close to the hand can have its foot below the bottom of the frame
    while its body fills half the picture, and a solution told it cannot see
    that glass would be wrong in the way that is hardest to notice.

    This is the frame and nothing else: it asks where the camera is pointed,
    not what is standing in the way. ``unhidden_share`` is the other half, and
    ``glasses_the_camera_can_see`` is both. They are kept apart because a solution planning
    where to look next needs the frame on its own — it can work out what the
    camera would be pointed at from a pose it has not driven to yet, with no
    list of glasses in hand.
    """
    eye, forward, right, up = _lens_axes(hand)
    foot = np.array([x, y, TABLE_TOP_Z])
    rise = np.array([0.0, 0.0, max(height, 0.0)])
    edge = math.tan(math.radians(WRIST_VIEW_FOVY_DEG) / 2)
    # The five half spaces the picture is: in front of the lens, and inside
    # each of the four sides. Each one is a plane through the eye, so a point
    # is inside it when its direction from the eye has a positive part along
    # the plane's normal. The glass is a straight line, so each half space is
    # one inequality in how far up the line you are, and what is left after all
    # five is the stretch of the glass that is in the picture.
    low, high = 0.0, 1.0
    for normal in (
        forward,
        edge * forward - right,
        edge * forward + right,
        edge * forward - up,
        edge * forward + up,
    ):
        at_foot = float((foot - eye) @ normal)
        along = float(rise @ normal)
        if abs(along) < 1e-12:
            if at_foot < 0.0:
                return False
            continue
        crosses = -at_foot / along
        if along > 0.0:
            low = max(low, crosses)
        else:
            high = min(high, crosses)
        if low > high:
            return False
    return low <= high


# A glass standing across the lens's own plane cannot be drawn in the picture
# at all, because half of it is behind the camera. It is also touching the
# camera, so it blots out everything behind it and nothing can blot out it.
# This stands for that: a patch larger than any picture.
WHOLE_PICTURE = (-1e6, 1e6, -1e6, 1e6)


def _picture_patch_of_glass(hand: Waypoint, glass: Seen) -> tuple[float, float, float, float]:
    """The patch of the picture a glass stands in: top row, bottom row, left column, right column.

    The glass is taken as the upright box its measurements describe: as wide as
    its widest, as tall as its height, facing the lens. ``WHOLE_PICTURE`` when it
    is level with the lens or wrapped around it.

    It is a box and not an outline because a box is what the arm's numbers add
    up to. ``Seen`` carries a height, a widest and a foot, and nothing about
    the shape between them, so a solution could not work out anything finer and
    neither should this.
    """
    eye, forward = lens_position_and_direction(hand)
    across = np.array([glass.x - eye[0], glass.y - eye[1]])
    range_to = float(np.linalg.norm(across))
    radius = max(glass.widest, 0.0) / 2
    if range_to <= radius:
        return WHOLE_PICTURE
    # Six points that between them reach every edge of the glass's outline: the
    # two it is touched by a line of sight either side, top and bottom, and the
    # two that reach furthest up and down the picture, which are the near edge
    # of the foot and the far edge of the rim. The sides are taken where the
    # line of sight grazes the glass and not across its middle, because a glass
    # the lens is nearly touching is far wider in the picture than its middle
    # is, and that glass — the one the hand is working on — is the one that
    # hides the most.
    bearing = math.atan2(float(across[1]), float(across[0]))
    grazing = math.asin(radius / range_to)
    reach = math.sqrt(range_to**2 - radius**2)
    tall = max(glass.height, 0.0)
    points = [
        (eye[0] + reach * math.cos(bearing + turn), eye[1] + reach * math.sin(bearing + turn), height)
        for turn in (-grazing, grazing)
        for height in (0.0, tall)
    ]
    points.append(
        (
            eye[0] + (range_to - radius) * math.cos(bearing),
            eye[1] + (range_to - radius) * math.sin(bearing),
            0.0,
        )
    )
    points.append(
        (
            eye[0] + (range_to + radius) * math.cos(bearing),
            eye[1] + (range_to + radius) * math.sin(bearing),
            tall,
        )
    )
    if min(float((np.array([x, y, TABLE_TOP_Z + z]) - eye) @ forward) for x, y, z in points) <= 1e-6:
        return WHOLE_PICTURE
    drawn = [table_point_to_pixel(hand, *point) for point in points]
    rows = [row for row, _ in drawn]
    columns = [column for _, column in drawn]
    return min(rows), max(rows), min(columns), max(columns)


def _overlap_area(box: tuple[float, float, float, float], other: tuple[float, float, float, float]) -> float:
    """How much of ``box`` lies inside ``other``, as rows by columns of the picture."""
    rows = min(box[1], other[1]) - max(box[0], other[0])
    columns = min(box[3], other[3]) - max(box[2], other[2])
    return max(rows, 0.0) * max(columns, 0.0)


def unhidden_share(hand: Waypoint, glass: Seen, others: Iterable[Seen]) -> float:
    """What share of a glass is not hidden behind a nearer glass, 0 to 1.

    Each glass stands in a patch of the picture, and a glass nearer the lens
    hides whatever stands in the same patch behind it. This is the share of a
    glass's own patch that no nearer glass covers — the part of it the camera
    has to measure the glass from.

    Three things about it are worth knowing.

    It is worked out from the **measured** place, width and height of every
    glass, the one doing the hiding included, because that is all the arm has.

    It is in the picture's own coordinates, not in the table's. A flat answer —
    which glass stands behind which, seen from above — is much easier to write
    and is wrong here, because the lens looks down on the table from above the
    rims and sees a far glass standing over a near one. Measured against the
    renderer's own account of what is in front of what, the flat rule hides
    glasses that the picture shows whole.

    Both patches are rectangles. The arm's numbers are a height, a width and a
    foot, so a rectangle is as fine a shape as a solution could work out, and
    this must not know more about the glass than the solution does. Held
    against the renderer's own account of which glass each pixel belongs to,
    over two tables from three poses each, the two agree to within a tenth of
    a glass on average, and the rule never kept a glass the renderer had left in
    slivers.

    A reading with no width at all is not one the camera could have taken, and
    there is no saying what is hidden of it, so it counts as nothing showing.
    """
    box = _picture_patch_of_glass(hand, glass)
    area = (box[1] - box[0]) * (box[3] - box[2])
    if area <= 0.0:
        return 0.0
    eye, _ = lens_position_and_direction(hand)
    range_to = math.hypot(glass.x - eye[0], glass.y - eye[1])
    in_front = []
    for other in others:
        if other.id == glass.id or math.hypot(other.x - eye[0], other.y - eye[1]) >= range_to:
            continue
        patch = _picture_patch_of_glass(hand, other)
        if _overlap_area(box, patch) > 0.0:
            in_front.append(patch)
    if not in_front:
        return 1.0
    # The nearer glasses can overlap each other, so the hidden part is the area
    # of their union inside this box. With a handful of glasses on a table the
    # plainest way is to cut the box along every edge they bring and add up the
    # pieces that any of them covers.
    edges_down = sorted({box[0], box[1], *(r for patch in in_front for r in patch[:2])})
    edges_across = sorted({box[2], box[3], *(c for patch in in_front for c in patch[2:])})
    covered = 0.0
    for top, bottom in zip(edges_down, edges_down[1:], strict=False):
        if bottom <= box[0] or top >= box[1]:
            continue
        for left, right in zip(edges_across, edges_across[1:], strict=False):
            if right <= box[2] or left >= box[3]:
                continue
            piece = (top, bottom, left, right)
            middle = ((top + bottom) / 2, (left + right) / 2)
            if any(
                patch[0] <= middle[0] <= patch[1] and patch[2] <= middle[1] <= patch[3] for patch in in_front
            ):
                covered += (piece[1] - piece[0]) * (piece[3] - piece[2])
    return max(0.0, 1.0 - covered / area)


def glasses_the_camera_can_see(hand: Waypoint, seen: Iterable[Seen]) -> tuple[Seen, ...]:
    """The glasses of ``seen`` the camera can really see from ``hand``.

    A glass is kept when it is **inside the frame** and **at least ``LEAST_VISIBLE_SHARE`` of it
    is not behind a nearer glass**. This is the rule the box model is trained to: its
    answer keys hold the glasses this keeps, and no others, so it learns to find what a
    camera could really measure.

    ``seen`` is what ``TableSimulator.look()`` returned, every glass still on the table, with
    problem 3's measuring error. This narrows that list and changes nothing in it. Every
    glass is judged by its measured place, height and width, so a reading a few
    millimetres out can put a glass on the wrong side of the edge of the frame, or of a
    neighbour. A glass that has gone over is judged as though it still stood.
    """
    glasses = tuple(seen)
    return tuple(
        glass
        for glass in glasses
        if in_camera_frame(hand, glass.x, glass.y, glass.height)
        and unhidden_share(hand, glass, glasses) >= LEAST_VISIBLE_SHARE
    )
