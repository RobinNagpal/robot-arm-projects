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

from dataclasses import dataclass

import numpy as np

from .profile import Profile

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


def glass_mask(rgb: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Which pixels are glass.

    In a real cell this is a trained segmentation model, and this function is
    where it would be called. In simulation it uses the property that makes
    glass hard in the first place: a depth camera cannot see it. Most of the
    light goes straight through and the rest is bent by the curved wall, so the
    depth picture has a hole exactly where the glass is.

    Reading the hole is therefore not a trick to get around the simulator. It
    is the same signal a real depth camera gives, and a pipeline built on it
    meets the same difficulty a real one does.
    """
    if rgb.shape[:2] != depth.shape[:2]:
        raise ValueError("the colour and depth pictures must be the same size")

    # Depth that is missing, zero, or absurdly far is depth that did not come
    # back. Through a glass, that is what happens.
    missing = ~np.isfinite(depth) | (depth <= 0.0)

    # A hole in the depth picture is only a glass if there is something to see
    # there. A hole over the empty background is just the far wall.
    lit = rgb.max(axis=2) > 25 if rgb.ndim == 3 else rgb > 25
    return missing & lit


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
            Detection(
                name=f"glass_{index - 1}",
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
    # pads, which is asked over the lower part, since that is where a grip
    # would go.
    lower = (0.05 * profile.total_height, 0.45 * profile.total_height)
    inside = (profile.height >= lower[0]) & (profile.height <= lower[1])
    if inside.sum() < 3:
        return None

    lean_deg = float(np.degrees(np.median(profile.slope()[inside])))
    return "tapered_glass" if lean_deg > TAPER_THRESHOLD_DEG else "straight_glass"
