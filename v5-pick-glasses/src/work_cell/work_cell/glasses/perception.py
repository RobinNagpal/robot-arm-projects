"""Turning a side-on picture of a glass into a measured profile.

The wrist camera is moved to one side of a glass and takes one picture. A
segmentation model says which pixels are glass. This module turns that mask
into widths in millimetres.

Two things make it possible.

A drinking glass is a solid of revolution, so the outline seen from any side is
the full shape: the width on screen at some height *is* the diameter there.

And the glass stands on the table, whose position the depth camera already
measured. That gives the distance from the wrist camera to the glass, and
distance is what turns an angle into a length. This is the one place where the
transparency of glass helps: the arm never needs a depth reading of the glass
itself, which it could not get, only of the table, which is opaque.

Plain numpy, no ROS, so the whole module can be tested with drawn masks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .profile import Profile

# A mask row with fewer than this many glass pixels is noise rather than glass.
MIN_ROW_PIXELS = 2

# The width profile is smoothed over this many rows before use. A segmentation
# edge wanders by a pixel or two, and an unsmoothed profile has a waist in
# every wobble.
SMOOTH_ROWS = 5

# How ragged a profile may be before it is not worth trusting. Measured as the
# average change in width from one row to the next, over the glass's own width.
# A clean silhouette sits near zero; a mask that caught a reflection jumps
# about.
MAX_RAGGEDNESS = 0.02

# The same limit said in pixels, for a glass too narrow in the picture for the
# fraction above to mean anything. Any mask edge wanders by about a pixel, and
# on a glass forty pixels wide that alone is two and a half per cent — so a
# fraction on its own throws out clean pictures of narrow glasses and keeps
# ragged pictures of wide ones. Whichever limit is the more forgiving wins.
RAGGED_PIXELS = 2.0


@dataclass(frozen=True)
class Intrinsics:
    """Pinhole camera parameters, in pixels."""

    fx: float
    fy: float
    cx: float
    cy: float

    @classmethod
    def from_camera_info(cls, msg) -> Intrinsics:
        k = msg.k
        return cls(fx=float(k[0]), fy=float(k[4]), cx=float(k[2]), cy=float(k[5]))


class NotMeasurable(Exception):
    """The picture could not be turned into a profile worth using."""


def row_widths(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The width in pixels of each row of the mask that holds any glass.

    The width is the distance from the leftmost glass pixel to the rightmost,
    not the number of glass pixels. A transparent object segments with holes in
    the middle — the model sees the table through it — and only the outline is
    wanted.

    Returns the row indices, top to bottom, and their widths.
    """
    if mask.ndim != 2:
        raise ValueError("a mask is a 2D array of booleans")

    filled = mask.astype(bool)
    counts = filled.sum(axis=1)
    rows = np.flatnonzero(counts >= MIN_ROW_PIXELS)
    if rows.size < 3:
        raise NotMeasurable("the mask holds almost no glass")

    widths = np.empty(rows.size, dtype=float)
    for index, row in enumerate(rows):
        columns = np.flatnonzero(filled[row])
        widths[index] = float(columns[-1] - columns[0] + 1)
    return rows, widths


def smooth(widths: np.ndarray, window: int = SMOOTH_ROWS) -> np.ndarray:
    """Median filter along the profile, to take the wobble out of an edge.

    A median rather than a mean, because a mean drags a real step — the top of
    a stem, where the bowl begins — out into a ramp, and the rules look for
    exactly that kind of step.
    """
    if window <= 1 or widths.size < window:
        return widths.astype(float)
    half = window // 2
    padded = np.pad(widths.astype(float), half, mode="edge")
    stacked = np.stack([padded[i : i + widths.size] for i in range(window)])
    return np.median(stacked, axis=0)


def raggedness(widths: np.ndarray) -> float:
    """How much the profile jumps about, relative to the glass's own width.

    Measured on the raw widths, before any smoothing, and used to decide
    whether a picture is worth trusting at all. A mask that caught a reflection
    flickers in and out down one side of the glass, which shows up here as a
    large average jump between neighbouring rows. The cheapest response is
    another picture from a different side.

    A clean silhouette sits near zero: the edge of a real mask wanders by about
    a pixel, which on a glass a hundred-odd pixels wide is well under a per
    cent.
    """
    if widths.size < 2:
        return float("inf")
    scale = float(np.median(widths))
    if scale <= 0:
        return float("inf")
    return float(np.abs(np.diff(widths)).mean() / scale)


def profile_from_mask(
    mask: np.ndarray,
    intrinsics: Intrinsics,
    distance: float,
    *,
    smooth_rows: int = SMOOTH_ROWS,
) -> Profile:
    """Measure a glass from one side-on silhouette.

    ``distance`` is from the camera to the glass, in metres, taken from where
    the table is. Because the glass axis is vertical and the camera looks
    horizontally at it, every part of the outline is at about that same
    distance, so one scale factor does for the whole picture. The parts nearer
    and further than the axis differ by the glass's own radius, which is a few
    per cent of the distance and less than the error in the mask edge.
    """
    if distance <= 0:
        raise ValueError("distance to the glass must be positive")

    rows, raw_px = row_widths(mask)

    # Judged before smoothing, deliberately. Smoothing is good enough to hide a
    # reflection that flickers down one side of the glass, and a profile that
    # only looks clean because it was filtered is not one to trust with a
    # grasp. So the raw edge decides whether the picture is worth using, and
    # the smoothed one is what gets measured.
    ragged = raggedness(raw_px)
    across = float(np.median(raw_px))
    limit = max(MAX_RAGGEDNESS, RAGGED_PIXELS / across) if across > 0 else MAX_RAGGEDNESS
    if ragged > limit:
        raise NotMeasurable(
            f"the outline is too ragged to measure ({ragged:.3f} against a limit of "
            f"{limit:.3f} for a glass {across:.0f} pixels across); the mask has probably "
            "caught a reflection or a neighbouring glass"
        )
    widths_px = smooth(raw_px, smooth_rows)

    # One pixel covers distance / focal_length metres at this range.
    metres_across = distance / intrinsics.fx
    metres_up = distance / intrinsics.fy

    # Rows count downwards in a picture and heights count upwards from the
    # table, so the bottom row of the mask is height zero.
    heights = (rows[-1] - rows) * metres_up
    widths = widths_px * metres_across

    order = np.argsort(heights)
    return Profile(heights[order], widths[order])


def handle_direction(front: Profile, side: Profile) -> float | None:
    """Whether the glass has a handle, and roughly where it points.

    A handle is the part of a glass that is not a solid of revolution, and that
    is exactly how it is found: take a second picture ninety degrees round, and
    if one view is wider than the other at the same height, the extra is a
    handle.

    Returns the angle in radians, relative to the direction the first picture
    was taken from, or None if the two views agree and the glass is plain.
    """
    common = min(front.total_height, side.total_height)
    if common <= 0:
        return None

    samples = np.linspace(0.0, common, 40)
    front_widths = np.array([front.width_at(h) for h in samples])
    side_widths = np.array([side.width_at(h) for h in samples])

    difference = front_widths - side_widths
    scale = float(max(front.max_width, side.max_width))
    # A handle adds a good fraction of the glass's own width to one view. Less
    # than a tenth is the two pictures disagreeing about an edge.
    if np.abs(difference).max() < 0.10 * scale:
        return None

    # The wider view is the one looking at the handle side-on, so the handle
    # points across that view.
    return 0.0 if difference.max() > -difference.min() else float(np.pi / 2)
