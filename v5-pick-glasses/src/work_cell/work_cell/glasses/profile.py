"""The width of a glass at every height, and the features found in it.

This is what the arm has instead of a table of measurements. A side-on picture
of a glass gives its outline, and reading the width off that outline at every
height gives a Profile. Everything the arm needs to know about a glass it has
never seen is worked out from this one list of numbers.

The features are deliberately described by shape rather than by size. "A local
minimum in width with wider parts above and below" is a stem on every stemmed
glass ever made. "Nine millimetres across, ninety millimetres up" is a stem on
exactly one.

Plain numpy, no ROS, so the whole module can be tested directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# How far off vertical a wall can lean and still be worth gripping.
#
# Two flat pads on a slope push the glass along that slope; on a vertical wall
# they just press. But a soft pad does not need a perfectly vertical wall — it
# squashes to fit. The figure that matters is how much it can squash across its
# own height, which for the silicone pads on this gripper is a little over a
# millimetre over a pad about 12 mm tall. That is atan(1.2 / 12), near enough
# six degrees.
#
# Setting it tighter than the pad can actually manage has a specific cost:
# every short glass with a mould taper gets refused, because a 10% taper over
# 55 mm of height is already more than two degrees. That is a real glass and
# the gripper can hold it perfectly well.
#
# This is a property of the gripper's pads, not of any glass, which is why it
# lives here rather than in a glass record.
VERTICAL_TOLERANCE = math.radians(6.0)

# Widths are compared after rounding to this, so that measurement noise does
# not invent a waist in a wall that is actually straight.
WIDTH_RESOLUTION = 0.0002  # 0.2 mm


@dataclass(frozen=True)
class Band:
    """A run of heights over which the wall is worth gripping."""

    bottom: float
    top: float

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def middle(self) -> float:
        return (self.bottom + self.top) / 2.0


@dataclass(frozen=True)
class Profile:
    """The width of one glass at every height, in metres.

    ``height`` runs from 0 at the table to the rim. ``width`` is the full
    diameter, not the radius, because that is what the fingers have to open to.
    """

    height: np.ndarray
    width: np.ndarray

    def __post_init__(self) -> None:
        height = np.asarray(self.height, dtype=float)
        width = np.asarray(self.width, dtype=float)
        if height.shape != width.shape:
            raise ValueError("height and width must be the same length")
        if height.size < 3:
            raise ValueError("a profile needs at least three samples")
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "width", width)

    # ------------------------------------------------------------- the basics

    @property
    def total_height(self) -> float:
        return float(self.height[-1])

    @property
    def rim_width(self) -> float:
        return float(self.width[-1])

    @property
    def base_width(self) -> float:
        return float(self.width[0])

    @property
    def max_width(self) -> float:
        """The widest the glass gets. This is what decides rack clearance."""
        return float(self.width.max())

    def width_at(self, height: float) -> float:
        return float(np.interp(height, self.height, self.width))

    # ----------------------------------------------------------- the features

    @property
    def widest_at(self) -> float:
        """The height of the widest point. Usually the rim, or a bowl."""
        return float(self.height[int(np.argmax(self.width))])

    def waist_at(self, below: float | None = None) -> float | None:
        """The height of the narrowest point below ``below``, if it is a waist.

        A waist is a local minimum with genuinely wider glass on both sides of
        it, which is what a stem is. A wall that simply narrows towards the
        bottom has its minimum at the very bottom and is not a waist, so this
        returns None for a straight or tapered glass, and that is how the two
        families are told apart without anybody saying which is which.
        """
        limit = self.widest_at if below is None else below
        inside = self.height < limit
        # Fewer than three samples below the widest point means there is no
        # room for a waist. That happens when the widest part is the base,
        # which is a glass this rule does not apply to.
        if inside.sum() < 3:
            return None

        widths = self.width[inside]
        heights = self.height[inside]

        # A stem is a run of constant width, not a single point, so the
        # narrowest reading is a plateau rather than a minimum. Take the
        # longest such run and return its middle, which is where the stem is
        # furthest from both the foot flare and the bowl.
        narrowest = float(widths.min())
        at_minimum = widths <= narrowest + WIDTH_RESOLUTION
        start = best_start = best_end = None
        for index, flag in enumerate(np.append(at_minimum, False)):
            if flag and start is None:
                start = index
            elif not flag and start is not None:
                if best_start is None or (index - start) > (best_end - best_start):
                    best_start, best_end = start, index
                start = None
        if best_start is None:
            return None

        # A plateau touching either end of the searched run is the run ending,
        # not a waist. Requiring glass on both sides is what makes this a test
        # of shape rather than of size.
        if best_start == 0 or best_end >= len(widths):
            return None
        flares_below = widths[:best_start].max() > narrowest + WIDTH_RESOLUTION
        flares_above = widths[best_end:].max() > narrowest + WIDTH_RESOLUTION
        if not (flares_below and flares_above):
            return None
        return float(heights[(best_start + best_end - 1) // 2])

    def slope(self) -> np.ndarray:
        """How far off vertical the wall leans at each height, in radians.

        Zero is a vertical wall. The sign is dropped, because a wall leaning in
        and a wall leaning out are equally bad for two flat pads.
        """
        # The wall moves out by half the width change, because width is a
        # diameter and the wall is one side of it.
        d_radius = np.gradient(self.width / 2.0)
        d_height = np.gradient(self.height)
        return np.abs(np.arctan2(d_radius, d_height))

    def vertical_bands(
        self, *, within: tuple[float, float] | None = None, tolerance: float = VERTICAL_TOLERANCE
    ) -> list[Band]:
        """Runs of height where the wall is within ``tolerance`` of vertical.

        ``within`` is a (bottom, top) pair in metres, used to look only at the
        part of the glass a rule cares about. Returned bottom to top.
        """
        upright = self.slope() <= tolerance
        if within is not None:
            bottom, top = within
            upright &= (self.height >= bottom) & (self.height <= top)

        bands: list[Band] = []
        start: int | None = None
        for index, flag in enumerate(upright):
            if flag and start is None:
                start = index
            elif not flag and start is not None:
                bands.append(Band(float(self.height[start]), float(self.height[index - 1])))
                start = None
        if start is not None:
            bands.append(Band(float(self.height[start]), float(self.height[-1])))
        return [band for band in bands if band.height > 0]

    def flattest_band(self, *, within: tuple[float, float], height: float) -> Band | None:
        """The ``height``-tall run inside ``within`` whose wall leans least.

        For a glass with no vertical section anywhere — a cone — there is still
        a best place to grip, and this finds it. Returns None if ``within`` is
        not even ``height`` tall.
        """
        bottom, top = within
        inside = (self.height >= bottom) & (self.height <= top)
        if inside.sum() < 2 or (top - bottom) < height:
            return None

        heights = self.height[inside]
        leans = self.slope()[inside]

        best_start, best_lean = None, math.inf
        for start_height in heights:
            end_height = start_height + height
            if end_height > heights[-1]:
                break
            window = (heights >= start_height) & (heights <= end_height)
            lean = float(leans[window].max())
            if lean < best_lean:
                best_start, best_lean = float(start_height), lean

        return None if best_start is None else Band(best_start, best_start + height)


def profile_from_outline(outline, samples: int | None = None) -> Profile:
    """Turn a generated Outline into the Profile the arm would have measured.

    Only used by the tests and by the simulation, where the true shape is
    known. On a real glass the profile comes from a camera.
    """
    height = np.asarray(outline.height, dtype=float)
    width = np.asarray(outline.radius, dtype=float) * 2.0
    if samples is not None:
        even = np.linspace(0.0, float(height[-1]), samples)
        width = np.interp(even, height, width)
        height = even
    return Profile(height, width)
