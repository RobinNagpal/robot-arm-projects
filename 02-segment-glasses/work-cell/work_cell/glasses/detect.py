"""Finding glasses in a picture, and deciding what kind each one is.

Two jobs, and they happen at different moments in the run.

**Finding** happens once from above: where are the glasses on the table, and
how wide is each footprint. Height is deliberately not part of the answer,
because from directly above a tall glass and a short one look the same. That is
all the next step needs, because the next step goes and looks from the side.

**Deciding the kind** happens afterwards, from the side-on measurement, and it
is worth saying why. A kind here is a *shape* — a tube, a cone, a bowl on a
stem — and the measured profile is exactly a description of that shape. So the
kind can be read off the profile with a few tests, and the project needs no
trained classifier at all.

That is also more honest than classifying from above. From overhead a tall
glass and a short one look almost identical, and a stem is invisible. Deciding
the kind from the thing that actually shows the shape means a glass is never
assigned a rule that its shape cannot support.

Only the mask uses a camera picture; everything else is arithmetic over a
profile. No ROS anywhere, so the whole module can be tested directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .profile import Profile

# How far above the table something has to stand before it counts as an object
# rather than as the table. Bigger than the noise on a depth reading and much
# smaller than the shortest glass, so nothing real falls between the two.
STANDING_CLEARANCE = 0.005

# A glass is classed as tapered if its wall leans more than this over the lower
# part of it. Below this it is straight enough for flat pads to press on
# without sliding, which is the only difference that matters to the gripper.
TAPER_THRESHOLD_DEG = 6.0

# A waist below this fraction of the glass's height is a short stem rather than
# a long one. The two want different search bands and different force caps,
# which is the only reason the distinction exists.
#
# This is the one place the classifier is asked to tell apart two things the
# silhouette barely separates. A wine glass's stem ends between a third and
# half way up; an Irish coffee glass's ends around a fifth of the way. Their
# midpoints land near 20-28% and 13% respectively, so this sits between them
# with room on both sides.
#
# What the silhouette genuinely cannot show is wall thickness, which is what
# sets the force cap. That is why the run weighs every glass and raises the
# squeeze from the measurement rather than trusting the kind for it.
SHORT_STEM_FRACTION = 0.17

# The part of the glass, as fractions of its own height, whose lean decides
# straight against tapered. Low down, because that is where a grip would go,
# and clear of the very bottom, where the foot rounds into the table.
LEAN_BAND = (0.05, 0.45)


@dataclass(frozen=True)
class Detection:
    """One glass seen from above: where it stands, and how wide its footprint is.

    There is no height here, and that is the point. An overhead camera sees a
    glass end-on, so the one thing it cannot report is how tall the glass is.
    Everything that needs the height gets it from the side-on measurement.

    The width is enough to keep the planner honest about where the glass is,
    and it is a lower bound rather than the widest part: a wine glass is wider
    at the bowl than at the foot it stands on.
    """

    name: str
    position: np.ndarray
    rough_width: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", np.asarray(self.position, dtype=float))


def standing_on_the_table(
    depth: np.ndarray,
    intrinsics,
    camera_to_world: np.ndarray,
    table_z: float,
    *,
    clearance: float = STANDING_CLEARANCE,
    tallest: float | None = None,
    within: tuple[float, float] | None = None,
) -> np.ndarray:
    """Which pixels are looking at something standing on the table.

    A depth picture is an ordinary image whose pixels hold a distance instead
    of a colour: for each one, how far the camera is from whatever that pixel
    is pointing at. Given the camera's own position and which way it is
    facing, that is enough to turn any pixel into a point in the room, and
    once a pixel is a point in the room the question "is this the table, or
    something standing on it?" is just its height.

    So a glass is a run of pixels whose points sit more than ``clearance``
    above the table top. The table itself comes out at zero and is dropped,
    and sky and anything else the camera got no distance for is dropped with
    it, because a pixel with no distance cannot be placed at all.

    Two optional bounds keep other standing things out. ``tallest`` drops
    anything reaching higher than the tallest glass the cell handles, which is
    mostly the arm's own fingers passing through the picture. ``within`` keeps
    only what lies in a band of distance from the camera, which is how the
    side-on view ignores the rack and the other glasses behind the one it came
    to measure: the arm chose how far to stand off, so it knows the distance
    the glass ought to be at.

    This works because a glass is an ordinary opaque object here — see the
    assumptions in ``problem-statement.md``. It would not work on real
    glassware, and what to do instead is discussed in
    ``docs/step1-approaches.md``.
    """
    depth = np.asarray(depth, dtype=float)
    if depth.ndim != 2:
        raise ValueError("a depth picture is a 2D array of distances")

    rows, columns = np.indices(depth.shape)
    # Where each pixel points, in the camera's own frame: x right, y down,
    # z forwards, and the stored distance is how far along z it went.
    forward = np.where(np.isfinite(depth), depth, 0.0)
    points = np.stack(
        [
            (columns - intrinsics.cx) / intrinsics.fx * forward,
            (rows - intrinsics.cy) / intrinsics.fy * forward,
            forward,
        ],
        axis=-1,
    )

    turn = np.asarray(camera_to_world, dtype=float)
    height = points @ turn[:3, :3].T[:, 2] + turn[2, 3]

    standing = np.isfinite(depth) & (depth > 0.0) & (height > table_z + clearance)
    if tallest is not None:
        standing &= height < table_z + tallest
    if within is not None:
        standing &= (depth >= within[0]) & (depth <= within[1])
    return standing


# Two sightings of the same glass, from cameras this far apart or less, are
# taken to be the same glass when the pictures are merged. Glasses are set out
# further apart than this, so it cannot join two of them into one.
SAME_GLASS = 0.04

# How far out finding the middle of a glass-shaped patch can be. The edge of a
# mask wanders, a silhouette is cut off at the edge of a picture, and the arm
# does not arrive exactly where it was sent. It is used to say how much a pair
# of sightings may disagree before the pair is not worth believing.
SIGHTING_ERROR = 0.010


def foot_of(
    mask: np.ndarray, to_world, table_z: float, *, edge_above: float = 0.0
) -> np.ndarray | None:
    """Where the glass in this side-on mask is standing, in the room.

    The one part of a glass whose position a single picture can fix exactly is
    the foot, because the foot is on the table and the table is a plane the
    camera already knows. Everything above it is guesswork without a second
    view; the foot is not.

    This is what turns a position good enough to look at a glass into one good
    enough to close on it. A stem is a few millimetres across, and the survey
    is not that sure of anything.

    The foot is taken by its two sides rather than by its lowest point. A foot
    is a disc, and the camera looks down on it at a slant, so its outline is an
    ellipse: the lowest row of that ellipse is the rim nearest the camera, not
    the middle of the glass. Reading the middle column off at that row mixes
    the two and lands a whole foot-radius short — about 20 mm on a wine glass,
    which is enough to close the fingers beside a stem instead of around it,
    and it lands short by the same amount every time, so nothing downstream
    looks wrong.

    The far left and far right of the ellipse are the two places where the
    line of sight grazes the disc side-on, and those sit at the middle's own
    distance. Halfway between them is the middle.

    ``edge_above`` is how far above the table the mask's bottom edge really
    is. A mask built from depth leaves out the first few millimetres of the
    glass, because nothing that low can be told apart from the table. The
    camera looks at the foot almost level, so projecting that edge onto the
    table instead of onto its own height throws the foot far behind the
    glass: 5 mm of clearance puts it about 19 mm out, enough to close the
    fingers on a chord of the glass rather than across it.
    """
    used = np.flatnonzero(mask.any(axis=0))
    if used.size == 0:
        return None

    # The bottom edge of the silhouette, column by column. Every pixel along it
    # is a place where the line of sight grazes the side of the base at the
    # edge's height, so each one projects onto that height exactly. Read
    # together they are the near half of the base, drawn in the room.
    bottom = {int(column): int(np.flatnonzero(mask[:, column])[-1]) for column in used}
    nearest = max(bottom, key=lambda column: bottom[column])

    # Outwards from the nearest point for as long as the edge stays joined up.
    # On a wine glass the bowl overhangs the foot, and under the overhang the
    # bottom edge jumps to the underside of the bowl, which is not on the
    # table and must not be read as though it were.
    span = [nearest]
    for step in (-1, 1):
        column = nearest + step
        while column in bottom and abs(bottom[column] - bottom[column - step]) <= 3:
            span.append(column)
            column += step

    edge_z = table_z + edge_above
    rim = np.array([to_world(float(c), float(bottom[c]), edge_z) for c in span], dtype=float)
    rim[:, 2] = table_z
    if len(rim) < 3:
        return rim.mean(axis=0) if len(rim) else None

    # The circle through them. Written out as least squares rather than taken
    # from a fitting library: with x^2 + y^2 = 2ax + 2by + c it is linear in
    # the three unknowns, and the middle is what (a, b) are.
    x, y = rim[:, 0], rim[:, 1]
    try:
        a, b, _ = np.linalg.lstsq(
            np.column_stack([2.0 * x, 2.0 * y, np.ones_like(x)]), x**2 + y**2, rcond=None
        )[0]
    except np.linalg.LinAlgError:
        return rim.mean(axis=0)
    return np.array([float(a), float(b), float(table_z)])


def the_one_in_the_middle(mask: np.ndarray) -> np.ndarray:
    """Just the glass the camera was aimed at, out of everything in the mask.

    A side-on picture catches whatever else is standing on the table behind
    and beside the glass being measured, and every one of them stands above
    the table too. Measured together they make one impossible glass: as tall
    as the picture and as wide as the table.

    The camera was pointed at one glass, so the one wanted is the one in the
    middle. Anything that does not reach the middle column belongs to some
    other glass and is dropped.
    """
    labels = _label(mask)
    if labels.max() < 1:
        return mask

    middle = mask.shape[1] / 2.0
    best, best_gap = None, None
    for index in range(1, labels.max() + 1):
        columns = np.argwhere(labels == index)[:, 1]
        # Nothing to choose by position alone, so it is the blob the middle
        # column falls inside, or failing that the nearest one to it.
        gap = 0.0 if columns.min() <= middle <= columns.max() else float(
            min(abs(columns.min() - middle), abs(columns.max() - middle))
        )
        size = int((labels == index).sum())
        if best_gap is None or (gap, -size) < best_gap:
            best, best_gap = index, (gap, -size)

    return labels == best


def where_they_stand(
    first: list[Detection],
    first_camera: np.ndarray,
    second: list[Detection],
    second_camera: np.ndarray,
    camera_height: float,
    *,
    tallest: float,
    tolerance: float = 0.02,
    notes: list[str] | None = None,
) -> list[Detection]:
    """Where the glasses really stand, from two pictures taken from above.

    One picture from above cannot say where a glass stands. ``find_glasses()``
    has to put the silhouette somewhere, and the only plane it knows is the
    table, so it lays the glass's widest part down on the table. That part is
    not on the table — it is ``h`` above it — and laying it down pushes it
    outwards, away from the point under the camera, by ``H / (H - h)``. The
    direction comes out right and the distance comes out too far.

    Two pictures fix it, because that same unknown ``h`` decides how far the
    glass appears to move when the camera moves. Slide the camera by a known
    ``d`` and a glass laid down on the table appears to move by ``d / k``,
    where ``k = (H - h) / H``. So the apparent movement measures ``k``, ``k``
    gives back the true position and the true width, and nothing about any
    glass had to be known in advance.

    A glass that only one of the two pictures caught is left out. Its height
    cannot be measured from one view, so where it stands is not known, and a
    guess would be worse than a gap: another station usually catches it.

    ``tallest`` is the tallest glass the cell handles, and it is what keeps two
    different glasses from being read as one. Pairing a glass in one picture
    with a *different* glass in the other produces an apparent movement that is
    still parallel to the baseline whenever the two stand apart along it — the
    one direction this method cannot tell from a difference in height. Such a
    pair satisfies every other test here and reports a position a hundred
    millimetres or more from any real glass. What gives it away is the height
    it implies, which is taller than any glass the cell is built for.
    """
    baseline = np.asarray(first_camera, dtype=float)[:2] - np.asarray(second_camera, dtype=float)[:2]
    span = float(np.dot(baseline, baseline))
    if span <= 0.0:
        raise ValueError("the two pictures were taken from the same place, so they say nothing new")
    if not 0.0 < tallest < camera_height:
        raise ValueError("the camera has to be above the tallest glass for a picture to mean anything")

    # h = camera_height * (1 - k), so the tallest glass allowed is the smallest
    # k allowed. Anything below this is two glasses being read as one.
    least_shrink = (camera_height - tallest) / camera_height

    candidates = []
    for one in first:
        for other in second:
            moved = (other.position[:2] - np.asarray(second_camera, dtype=float)[:2]) - (
                one.position[:2] - np.asarray(first_camera, dtype=float)[:2]
            )
            travelled = float(np.dot(moved, moved))
            if travelled <= 0.0:
                continue

            # Least squares, because the two are parallel only up to the error
            # in either sighting.
            shrink = float(np.dot(baseline, moved)) / travelled

            # A shrink over 1 says the glass is below the table, which it is
            # not. It says instead that this glass is short enough to have
            # almost no lean to measure, and that the little there is has been
            # swamped by the error in finding its middle. Believing that much
            # is right — a short glass is nearly where a single picture puts
            # it — so it is taken as standing on the table rather than thrown
            # away. How far over 1 is forgiven depends on how far the glass
            # appeared to move: the same few millimetres of error matter more
            # when there is less movement to measure them against.
            slack = SIGHTING_ERROR / math.sqrt(travelled)
            if 1.0 < shrink <= 1.0 + slack:
                shrink = 1.0

            residual = float(np.linalg.norm(baseline - shrink * moved))
            if notes is not None:
                notes.append(
                    f"{one.name} in the first picture against {other.name} in the "
                    "second: it appears to move "
                    f"{float(np.linalg.norm(moved)) * 1000:.0f} mm while the camera moved "
                    f"{float(np.linalg.norm(baseline)) * 1000:.0f} mm, so shrink={shrink:.3f} "
                    f"(allowed {least_shrink:.3f} to 1.000) and residual="
                    f"{residual * 1000:.1f} mm (allowed {tolerance * 1000:.0f} mm)"
                    + _verdict(shrink, least_shrink, residual, tolerance)
                )
            if not least_shrink <= shrink <= 1.0:
                continue
            if residual > tolerance:
                continue
            candidates.append((residual, one, other, shrink))

    found: list[Detection] = []
    taken_first: set[int] = set()
    taken_second: set[int] = set()
    for _residual, one, other, shrink in sorted(candidates, key=lambda row: row[0]):
        if id(one) in taken_first or id(other) in taken_second:
            continue
        taken_first.add(id(one))
        taken_second.add(id(other))

        # Both pictures place it; averaging them costs nothing and halves the
        # effect of a ragged edge on either one.
        from_first = np.asarray(first_camera, dtype=float)[:2] + shrink * (
            one.position[:2] - np.asarray(first_camera, dtype=float)[:2]
        )
        from_second = np.asarray(second_camera, dtype=float)[:2] + shrink * (
            other.position[:2] - np.asarray(second_camera, dtype=float)[:2]
        )
        middle = (from_first + from_second) / 2.0

        found.append(
            Detection(
                name=one.name,
                position=np.array([middle[0], middle[1], float(one.position[2])]),
                # The width was laid down on the table with the rest of the
                # glass, so it is too big by the same factor.
                rough_width=shrink * (one.rough_width + other.rough_width) / 2.0,
            )
        )

    return found


def _verdict(shrink: float, least: float, residual: float, tolerance: float) -> str:
    """Why a pair was turned down, in words, for the run report."""
    if shrink > 1.0:
        return (
            " — REJECTED: shrink this far over 1 would put the glass below the table, and "
            "further over than the error in finding its middle can account for."
        )
    if shrink < least:
        return " — REJECTED: shrink that small means something taller than any glass here."
    if residual > tolerance:
        return " — REJECTED: the two sightings do not lie along the line the camera moved."
    return " — accepted"


def merge_sightings(found: list[Detection], *, apart: float = SAME_GLASS) -> list[Detection]:
    """One entry per glass, from stations whose pictures overlap.

    Renamed in a fixed order rather than in the order they were seen, so that
    the same table gives the same names whichever station happened to catch
    which glass first.
    """
    kept: list[Detection] = []
    for one in found:
        for index, already in enumerate(kept):
            if float(np.linalg.norm(already.position[:2] - one.position[:2])) <= apart:
                kept[index] = Detection(
                    name=already.name,
                    position=(already.position + one.position) / 2.0,
                    rough_width=max(already.rough_width, one.rough_width),
                )
                break
        else:
            kept.append(one)

    kept.sort(key=lambda d: (round(float(d.position[0]), 3), round(float(d.position[1]), 3)))
    return [
        Detection(name=f"glass_{index}", position=d.position, rough_width=d.rough_width)
        for index, d in enumerate(kept)
    ]


def find_glasses(mask: np.ndarray, to_world, table_z: float, min_pixels: int = 150) -> list[Detection]:
    """Group a mask into one detection per glass, seen from above.

    ``to_world`` turns a pixel and a height into a point in the room, by
    following the ray through that pixel until it meets the table. That is how
    a glass gets a position without a depth reading, which through glass there
    is none of.

    Only the position and the footprint width are wanted. How tall the glass is
    and what kind it is both get decided later, from the side view.
    """
    labels = _label(mask)
    found: list[Detection] = []
    for index in range(1, labels.max() + 1):
        pixels = np.argwhere(labels == index)
        if len(pixels) < min_pixels:
            continue
        row, column = pixels.mean(axis=0)
        position = np.asarray(to_world(float(column), float(row), table_z), dtype=float)

        # The width comes from putting the two edges of the blob on the table
        # and measuring between them, not from counting pixels and scaling.
        # Pixels only become millimetres once they have been placed somewhere.
        #
        # The half-pixel either side is not fussiness: a pixel's world position
        # is its centre, so the outside of the leftmost pixel is half a pixel
        # further left. Without it every width comes out one pixel short.
        left = float(pixels[:, 1].min()) - 0.5
        right = float(pixels[:, 1].max()) + 0.5
        edges = [np.asarray(to_world(edge, float(row), table_z), dtype=float) for edge in (left, right)]

        found.append(
            # Named for the patch it came from, not for a glass. Nothing here
            # knows yet whether two patches in two pictures are one glass or
            # two, and calling them glasses in the run report before that is
            # settled is how a reader ends up counting the same glass twice.
            Detection(
                name=f"patch_{index - 1}",
                position=position,
                rough_width=float(np.linalg.norm(edges[1] - edges[0])),
            )
        )
    return found


def _label(mask: np.ndarray) -> np.ndarray:
    """Number the separate blobs in a mask, without pulling in OpenCV.

    A flood fill from each unvisited pixel. Small pictures and a handful of
    glasses, so the simple version is fast enough and has no dependency.
    """
    labels = np.zeros(mask.shape, dtype=int)
    current = 0
    for start in np.argwhere(mask):
        if labels[tuple(start)]:
            continue
        current += 1
        stack = [tuple(start)]
        while stack:
            row, column = stack.pop()
            if not (0 <= row < mask.shape[0] and 0 <= column < mask.shape[1]):
                continue
            if labels[row, column] or not mask[row, column]:
                continue
            labels[row, column] = current
            stack.extend(
                [(row + 1, column), (row - 1, column), (row, column + 1), (row, column - 1)]
            )
    return labels


def classify(profile: Profile) -> str | None:
    """Which kind of glass this profile describes, or None if no kind fits.

    The tests are in the order that matters, because they overlap. A stemmed
    glass also has a sloping bowl, so looking for a stem first stops it being
    called tapered.

    Returning None is a real answer. It means a shape none of the rules
    describe, and the right response further up is to leave the glass standing
    and say so, rather than force it into the nearest kind.
    """
    waist = profile.waist_at()
    if waist is not None:
        fraction = waist / profile.total_height
        return "short_stemmed_glass" if fraction < SHORT_STEM_FRACTION else "stemmed_glass"

    # No stem. Now the question is whether the wall is upright enough for flat
    # pads.
    lean_deg = wall_lean_deg(profile)
    if lean_deg is None:
        return None
    return "tapered_glass" if lean_deg > TAPER_THRESHOLD_DEG else "straight_glass"


def wall_lean_deg(profile: Profile) -> float | None:
    """How far the lower wall leans off upright, in degrees, or None if too short to say.

    Asked over LEAN_BAND of the glass's own height, since that is where a grip
    would go. The median, so that one kink in the wall does not decide it.
    """
    low, high = (fraction * profile.total_height for fraction in LEAN_BAND)
    inside = (profile.height >= low) & (profile.height <= high)
    if inside.sum() < 3:
        return None
    return float(np.degrees(np.median(profile.slope()[inside])))
