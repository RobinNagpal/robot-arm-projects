"""The camera the arm carries, and what it can see from where the jaw stands.

This is the whole difference between problem 3 and problem 4. Problem 3 has a
camera bolted above the table that frames the glass zone on every table and
never moves, so a solution is handed the whole table for nothing. Here the
camera rides on the wrist, a hand's length behind the fingertips. It sees the
patch of table the jaw is pointing at and no more, so a solution that wants to
know what is in the far corner has to take the arm there and pay for the trip
in arm time. That is what a real cell is like; the overhead camera is a
convenience of the simulator.

**Glasses hide each other, and that is what makes one look not enough.** The
glass zone is only 320 by 360 mm and this lens is as wide as a real one, so
the floor of the zone does fit in a single frame: from travel height, with the
jaw at the near edge of the zone pointing across it, every point of it is in
frame. What does not fit is the glasses. They stand in each other's way, and
the ones that stand in each other's way most are the crowded ones a solution
has come to separate. Measured over eight drawn tables: a look from the near
edge of the zone hands over 83% of the glasses on the table and a look from
the middle 85%, the middling pose over the whole table hands over 20%, and it
takes two looks from different places to read every glass on all eight. Worse
for a solution, and deliberately: **it cannot tell that a glass is hidden**,
because a hidden glass is simply not in the list. So a solution that wants to
be sure has to look from somewhere else, and pay the arm time to get there.

Three things come out of this module and the first two answer the same
question in two forms. ``WristCamera.view()`` renders the patch for the
solutions that read pictures, and ``in_picture()`` says which glasses the
camera can really see for the solutions that read numbers. They share one
piece of geometry, so the two kinds of solution are told the same thing about
the table. ``WristCamera.labels()`` is the third and is for the tests: it asks
the renderer itself which glass each pixel belongs to, which is how the rule
about what hides what is held to the picture.

    from simulator import Simulator
    from wrist import WristCamera, in_picture

    table = Simulator(10_000)
    camera = WristCamera(table)        # keep one per table; building it is slow
    picture = camera.view(jaw)
    seen = in_picture(jaw, table.look())

Nothing here moves the table or the arm. A look is a question about a pose,
and the pose comes from the caller, because the simulator parks the jaw body away
from the table between actions and so cannot be asked where the jaw "is".
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable

import mujoco
import numpy as np
from work_cell.table.layout import TABLE_TOP_Z

from partners import (
    JAW_HALF_HEIGHT,
    TOOL_LENGTH,
    TOP_VIEW_FOVY_DEG,
    TOP_VIEW_SIZE,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Seen,
    Waypoint,
)
from simulator import Simulator

__all__ = [
    "CAMERA_BACK",
    "CAMERA_PITCH_DEG",
    "CAMERA_UP",
    "SEEN_SHARE",
    "WRIST_VIEW_FOVY_DEG",
    "WRIST_VIEW_SIZE",
    "WristCamera",
    "camera_pose",
    "in_picture",
    "sees",
    "showing",
    "to_pixel",
    "wrist_view",
]

# ------------------------------------------------------------------ the mounting
#
# Where the camera is bolted, measured from the fingertips in the jaw's own
# axes: back along the push, and up from the middle of the jaw.
#
# **Behind the hand, and above it.** The gripper is not a blade. Rolled on its
# side for a push it is still a 75 by 85 mm body with two fingers standing
# 69 mm above the middle of the jaw, and anything bolted in front of or beside
# that body is looking through it. So the camera goes on the wrist, behind the
# whole hand, on a bracket that stands clear above the fingers: the furthest
# back and the highest point of the tool, and the one with the least of the
# hand between it and the table. Both numbers are the tool's own, so if the
# hand ever changes the mounting follows it — back as far as the middle of the
# wrist box, and up by how far the fingers reach above the jaw's middle plus
# the thickness of the wrist.
#
# Two honest notes. The bracket rides in the same column of air as the gripper
# body, behind the fingers, so it reaches nothing the hand has not already
# struck. And the hand is in none of these pictures whatever the mounting,
# because the simulator parks the jaw body away from the table between actions, so
# here the mounting decides where the lens is and not what blocks it. On a real
# arm it would decide both, and that is what it was chosen for.
CAMERA_BACK = TOOL_LENGTH - WRIST_LENGTH / 2
CAMERA_UP = JAW_HALF_HEIGHT + WRIST_ACROSS / 2

# ------------------------------------------------------------------- the aiming
#
# How far the camera is tipped down from level, degrees. Forward and down in
# equal parts, and the reason is the height band the jaw lives in: a waypoint's
# z runs from PUSH_HEIGHT (75 mm) to TRAVEL_HEIGHT (300 mm) above the table
# top, so the lens is never lower than 190 mm above the table and never higher
# than 410 mm. At 45 degrees the middle of the picture lands on the table the
# lens's own height ahead of it, which keeps the picture on the table at both
# ends of that band: pushing, it holds the feet of the glasses around the jaw,
# out to 330 mm ahead of the fingertips and 260 mm across; travelling, it holds
# a patch 570 mm across, wider than the glass zone, with whole glasses in it.
# Tipped less the picture runs off the end of the table — at 35 degrees from
# travel height, a quarter of it is background — and tipped more, at 55, the
# glasses are cut off at the rim while the near table below them is empty.
# All three were rendered and looked at before this was written.
CAMERA_PITCH_DEG = 45.0

# The picture is the size and the angle of problem 3's straight-down view, on
# purpose and not by coincidence. The size is the brief's: a learned solution
# fitted on problem 3 meets the same shaped array here. The angle is borrowed
# for the same reason one step further on — at travel height it makes a wrist
# picture cover a patch of table of the same order as the overhead one, so the
# glasses are about the size the policy saw them before. It is deliberately not
# a new number invented for this problem.
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
SEEN_SHARE = 0.5


def camera_pose(jaw: Waypoint) -> tuple[np.ndarray, np.ndarray]:
    """Where the lens is in the world, and the way it points.

    ``jaw`` is a waypoint, so its ``z`` is measured from the table top and its
    ``heading`` is the way the fingertips point. Returns the eye in world
    metres and a unit vector along the camera's axis.
    """
    ahead = np.array([math.cos(jaw.heading), math.sin(jaw.heading), 0.0])
    fingertips = np.array([jaw.x, jaw.y, TABLE_TOP_Z + jaw.z])
    eye = fingertips - CAMERA_BACK * ahead + np.array([0.0, 0.0, CAMERA_UP])
    tipped = math.radians(CAMERA_PITCH_DEG)
    forward = np.array([*(math.cos(tipped) * ahead[:2]), -math.sin(tipped)])
    return eye, forward


def _axes(jaw: Waypoint) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The eye and the camera's three axes: forward, right in the picture, up in the picture.

    The camera does not roll — its up stays as near the world's up as it can —
    because the arm only ever turns the hand about the vertical.
    """
    eye, forward = camera_pose(jaw)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    return eye, forward, right, np.cross(right, forward)


class WristCamera:
    """The camera on one table's arm. Building it is slow; keep it.

    A renderer holds a graphics context, so make one per table and call
    ``view()`` as often as the solution looks. The camera itself is moved on
    every call, which is the whole point of it.
    """

    def __init__(self, simulator: Simulator) -> None:
        self.simulator = simulator
        self.renderer = mujoco.Renderer(simulator.model, *WRIST_VIEW_SIZE)
        # Problem 3's overhead camera is written into the world XML and cannot
        # be moved, and problem 3 is not being edited. A free camera is not in
        # the world at all: it is placed per call, so one world serves both.
        self.camera = mujoco.MjvCamera()
        self.camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        # Which glass each geom of the world belongs to, for ``labels``. The
        # table, the jaw and the sky are all -1.
        self.glass_of_geom = np.full(simulator.model.ngeom, -1, dtype=int)
        for glass, body in enumerate(simulator.bodies):
            self.glass_of_geom[simulator.model.geom_bodyid == body] = glass

    def view(self, jaw: Waypoint) -> np.ndarray:
        """The table from the jaw's pose, right now. See ``wrist_view`` for the shape and colours."""
        started = time.perf_counter()
        self._point(jaw)
        # MuJoCo keeps a free camera's angle of view in the model and nowhere
        # else, so it is set for this render and put back. film.py renders the
        # same kind of camera and would otherwise be reframed by a look.
        model = self.simulator.model
        was = model.vis.global_.fovy
        model.vis.global_.fovy = WRIST_VIEW_FOVY_DEG
        try:
            self.renderer.update_scene(self.simulator.data, self.camera)
            picture = self.renderer.render().copy()
        finally:
            model.vis.global_.fovy = was
        # Rendering is the examiner's cost, not the solution's thinking time.
        self.simulator.seconds += time.perf_counter() - started
        return picture

    def labels(self, jaw: Waypoint) -> np.ndarray:
        """Which glass each pixel of that same picture belongs to, or -1 for anything else.

        **This is not something a solution is given.** A real camera has no
        such picture and the contract has nowhere to put one. It is here
        because ``showing`` works out what hides what from a few measured
        numbers, and this is the renderer's own answer to the same question,
        which is what the tests hold the rule against.
        """
        started = time.perf_counter()
        self._point(jaw)
        model = self.simulator.model
        was = model.vis.global_.fovy
        model.vis.global_.fovy = WRIST_VIEW_FOVY_DEG
        try:
            self.renderer.enable_segmentation_rendering()
            self.renderer.update_scene(self.simulator.data, self.camera)
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

    def _point(self, jaw: Waypoint) -> None:
        """Put the free camera where the jaw's pose says the lens is."""
        eye, forward = camera_pose(jaw)
        if eye[2] <= TABLE_TOP_Z:
            raise ValueError(f"the camera is {1000 * (TABLE_TOP_Z - eye[2]):.0f} mm below the table top")
        # A free camera is described by the point it looks at and how far away
        # it is, so the axis is followed to the table and that point is used.
        # It is also what the middle pixel shows, which makes the camera easy
        # to check against a render.
        reach = (eye[2] - TABLE_TOP_Z) / math.sin(math.radians(CAMERA_PITCH_DEG))
        self.camera.lookat[:] = eye + reach * forward
        self.camera.distance = reach
        self.camera.azimuth = math.degrees(jaw.heading)
        self.camera.elevation = -CAMERA_PITCH_DEG

    def close(self) -> None:
        self.renderer.close()


def wrist_view(simulator: Simulator, jaw: Waypoint) -> np.ndarray:
    """The table as the arm's own camera sees it, as an array a policy can take.

    **Shape** ``WRIST_VIEW_SIZE + (3,)``, that is ``(384, 384, 3)``, ``uint8``,
    the same as problem 3's straight-down view.

    **Colours** red, green, blue in that order, 0 to 255. The same world and
    the same lighting as ``top_view``: warm tan table, every glass the same
    pale blue, shaded, so a glass pixel's blue is above its red and a lit table
    pixel's never is. Unlike the straight-down view this one can see past the
    edge of the table, and what is beyond it is black.

    **Where the camera is** on the wrist, ``CAMERA_BACK`` behind the fingertips
    and ``CAMERA_UP`` above the middle of the jaw, tipped ``CAMERA_PITCH_DEG``
    down from level and pointing the way the jaw points. It moves with the jaw,
    so no two looks from different poses are the same picture.

    **What is in frame** the patch of table the camera is aimed at, and nothing
    else. How big that patch is depends on how high the jaw is standing, which
    is the cost the problem is built around: at PUSH_HEIGHT it is about 260 mm
    across and the taller glasses are cut off at the rim, and at TRAVEL_HEIGHT
    it is about 570 mm across with whole glasses in it. To see more, lift the
    jaw or drive it somewhere else, and pay the arm time. The glasses in that
    patch stand in front of one another as they really do, which ``in_picture``
    accounts for and this picture simply shows.

    **Which way round** the middle of the picture is the point on the table the
    axis meets, which lies ahead of the fingertips. Up the picture is further
    away, right is the jaw's right. ``to_pixel`` is that mapping; use it rather
    than rederiving it.

    **What is not in it** the arm. The simulator parks the jaw body clear of the
    table between actions, so the hand is never in its own picture. A real
    wrist camera sees its fingers at the edge of the frame.

    Building a renderer is slow. In a loop keep a ``WristCamera`` instead.
    """
    camera = WristCamera(simulator)
    try:
        return camera.view(jaw)
    finally:
        camera.close()


def to_pixel(jaw: Waypoint, x: float, y: float, z: float = 0.0) -> tuple[float, float]:
    """Where a point in the world falls in the picture: (row, column), fractional.

    ``x`` and ``y`` are metres on the table and ``z`` is height above the table
    top, as a waypoint's is. Outside 0..383 for a point outside the frame, and
    meaningless for a point behind the lens, which ``sees`` is for.
    """
    eye, forward, right, up = _axes(jaw)
    rows, columns = WRIST_VIEW_SIZE
    towards = np.array([x, y, TABLE_TOP_Z + z]) - eye
    # How far across and up the point is, as a fraction of the half frame at
    # its own depth. The frame is square, so one angle serves both directions.
    half = float(towards @ forward) * math.tan(math.radians(WRIST_VIEW_FOVY_DEG) / 2)
    across = float(towards @ right) / half
    upward = float(towards @ up) / half
    return (1.0 - upward) / 2.0 * rows - 0.5, (1.0 + across) / 2.0 * columns - 0.5


def sees(jaw: Waypoint, x: float, y: float, height: float = 0.0) -> bool:
    """Is a glass standing at ``x, y`` and ``height`` tall inside the picture?

    The glass is treated as the upright line from its foot on the table top to
    the middle of its rim, and it counts as seen when any part of that line is
    inside the camera's frustum. The line and not the foot alone, because a
    glass close to the jaw can have its foot below the bottom of the frame
    while its body fills half the picture, and a solution told it cannot see
    that glass would be wrong in the way that is hardest to notice.

    This is the frame and nothing else: it asks where the camera is pointed,
    not what is standing in the way. ``showing`` is the other half, and
    ``in_picture`` is both. They are kept apart because a solution planning
    where to look next needs the frame on its own — it can work out what the
    camera would be pointed at from a pose it has not driven to yet, with no
    list of glasses in hand.
    """
    eye, forward, right, up = _axes(jaw)
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
EVERYTHING = (-1e6, 1e6, -1e6, 1e6)


def _silhouette(jaw: Waypoint, glass: Seen) -> tuple[float, float, float, float]:
    """The patch of the picture a glass stands in: top row, bottom row, left column, right column.

    The glass is taken as the upright box its measurements describe: as wide as
    its widest, as tall as its height, facing the lens. ``EVERYTHING`` when it
    is level with the lens or wrapped around it.

    It is a box and not an outline because a box is what the arm's numbers add
    up to. ``Seen`` carries a height, a widest and a foot, and nothing about
    the shape between them, so a solution could not work out anything finer and
    neither should this.
    """
    eye, forward = camera_pose(jaw)
    across = np.array([glass.x - eye[0], glass.y - eye[1]])
    range_to = float(np.linalg.norm(across))
    radius = max(glass.widest, 0.0) / 2
    if range_to <= radius:
        return EVERYTHING
    # Six points that between them reach every edge of the glass's outline: the
    # two it is touched by a line of sight either side, top and bottom, and the
    # two that reach furthest up and down the picture, which are the near edge
    # of the foot and the far edge of the rim. The sides are taken where the
    # line of sight grazes the glass and not across its middle, because a glass
    # the lens is nearly touching is far wider in the picture than its middle
    # is, and that glass — the one the jaw is working on — is the one that
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
    points.append((eye[0] + (range_to - radius) * math.cos(bearing),
                   eye[1] + (range_to - radius) * math.sin(bearing), 0.0))
    points.append((eye[0] + (range_to + radius) * math.cos(bearing),
                   eye[1] + (range_to + radius) * math.sin(bearing), tall))
    if min(float((np.array([x, y, TABLE_TOP_Z + z]) - eye) @ forward) for x, y, z in points) <= 1e-6:
        return EVERYTHING
    drawn = [to_pixel(jaw, *point) for point in points]
    rows = [row for row, _ in drawn]
    columns = [column for _, column in drawn]
    return min(rows), max(rows), min(columns), max(columns)


def _overlap(box: tuple[float, float, float, float], other: tuple[float, float, float, float]) -> float:
    """How much of ``box`` lies inside ``other``, as rows by columns of the picture."""
    rows = min(box[1], other[1]) - max(box[0], other[0])
    columns = min(box[3], other[3]) - max(box[2], other[2])
    return max(rows, 0.0) * max(columns, 0.0)


def showing(jaw: Waypoint, glass: Seen, others: Iterable[Seen]) -> float:
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
    box = _silhouette(jaw, glass)
    area = (box[1] - box[0]) * (box[3] - box[2])
    if area <= 0.0:
        return 0.0
    eye, _ = camera_pose(jaw)
    range_to = math.hypot(glass.x - eye[0], glass.y - eye[1])
    in_front = []
    for other in others:
        if other.id == glass.id or math.hypot(other.x - eye[0], other.y - eye[1]) >= range_to:
            continue
        patch = _silhouette(jaw, other)
        if _overlap(box, patch) > 0.0:
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
                patch[0] <= middle[0] <= patch[1] and patch[2] <= middle[1] <= patch[3]
                for patch in in_front
            ):
                covered += (piece[1] - piece[0]) * (piece[3] - piece[2])
    return max(0.0, 1.0 - covered / area)


def in_picture(jaw: Waypoint, seen: Iterable[Seen]) -> tuple[Seen, ...]:
    """The glasses of ``seen`` the camera can really see from ``jaw``.

    A glass is kept when it is **inside the frame** and **at least
    ``SEEN_SHARE`` of it is not behind a nearer glass**. The second half
    is what makes one look from the edge of the table not enough: the glasses
    that hide each other are the crowded ones standing close and in line, and
    those are exactly the ones a solution needs to see, so it has to move the
    arm round the group and pay for the trip.

    ``seen`` is what ``Simulator.look()`` returned, which is every glass still on
    the table, measured with problem 3's error. This narrows that list and
    changes nothing in it: the readings handed back are the same readings, with
    the same noise, in the same order. Problem 4 takes the overhead camera
    away; it does not re-measure the table, and a solution comparing two looks
    of the same glass must still see problem 3's error between them.

    Every glass is judged by its **measured** place, height and width, because
    that is all the arm knows. A reading that is 2 mm out can therefore put a
    glass on the wrong side of the edge of the frame, or of a neighbour, which
    is correct: the arm cannot tell either.

    A glass that has gone over is judged as though it still stood, so what is
    really tested is the patch of table it lies on, and it hides what stands
    behind it as though it still stood too. The arm has no measurement of which
    way a fallen glass points, and ``Seen.standing`` already tells a solution
    that it is down.
    """
    glasses = tuple(seen)
    return tuple(
        glass
        for glass in glasses
        if sees(jaw, glass.x, glass.y, glass.height) and showing(jaw, glass, glasses) >= SEEN_SHARE
    )
