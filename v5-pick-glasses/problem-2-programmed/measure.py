"""Step 3: measure a glass from one side picture, and say if the picture is bad.

Problem 1's silhouette, then two corrections the silhouette leaves out:

**The height.** The camera looks level from MEASURE_VIEW_HEIGHT. Above that
height the top edge of the outline is the near side of the rim, which is
closer to the camera than the axis, so it reads high. Below it, the bottom
edge is the near side of the foot, which reads low. Both are a known distance
nearer, so both can be undone. Uncorrected, a tall glass reads 5–13 mm tall.

**The width.** A round glass's outline is where the lines from the camera
just touch it, a little outside its true width. Under a millimetre; undone
anyway, since it is one line.
"""

from __future__ import annotations

import numpy as np
from work_cell.arm.dimensions import MEASURE_VIEW_HEIGHT
from work_cell.glasses.detect import STANDING_CLEARANCE, standing_on_the_table, the_one_in_the_middle
from work_cell.glasses.perception import NotMeasurable, profile_from_mask
from work_cell.glasses.profile import Profile
from work_cell.table.layout import TABLE_TOP_Z

from find import Seen
from render import LENS, STANDOFF, Picture
from views import DEPTH_BAND

# How far the widest width seen from the side may differ from the one seen
# from above before one of the two pictures is not believed.
AGREEMENT = 0.006

# Which part of the outline gives the rim's and the foot's widths, as
# fractions of the measured height. The very top and bottom rows are the
# narrow ends of the rim's and foot's ellipses, not their widths.
RIM_PART, FOOT_PART = 0.90, 0.05


def outline(picture: Picture) -> np.ndarray:
    """The mask of the glass in the middle of the picture."""
    standing = standing_on_the_table(
        picture.depth,
        LENS,
        picture.camera_to_world,
        TABLE_TOP_Z,
        within=(STANDOFF - DEPTH_BAND, STANDOFF + DEPTH_BAND),
    )
    return the_one_in_the_middle(standing)


def corrected(profile: Profile) -> Profile:
    """Undo the rim and foot being nearer than the axis. See the module notes."""
    s, lens_height = STANDOFF, MEASURE_VIEW_HEIGHT
    measured = profile.total_height
    rim = profile.width[profile.height >= RIM_PART * measured].max() / 2
    foot = profile.width[profile.height <= FOOT_PART * measured].max() / 2

    # How far below the lens the bottom row is, at the axis's distance. The
    # bottom row is the foot's near edge, just above STANDING_CLEARANCE:
    # anything lower is dropped as table.
    below = s * (lens_height - STANDING_CLEARANCE) / (s - foot)
    if measured > below:
        # The rim is above the lens: its near edge is what shows.
        top = lens_height + (measured - below) * (s - rim) / s
    else:
        # The rim is below the lens: the camera looks down on it, and the far
        # edge is what shows.
        top = lens_height - (below - measured) * (s + rim) / s

    # Every other row is the glass's side, at the axis's distance, so it only
    # needs moving to where the lens really is. Rows past the top are the rim
    # seen end-on.
    height = np.clip(profile.height + lens_height - below, 0.0, None)
    keep = height < top
    slope = profile.width[keep] / (2 * s)
    width = 2 * s * slope / np.sqrt(1 + slope**2)
    return Profile(np.append(height[keep], top), np.append(width, width[-1]))


def measure(picture: Picture, seen: Seen) -> Profile:
    """A corrected profile, or NotMeasurable saying why the picture is bad."""
    mask = outline(picture)
    if mask[0].any() or mask[:, 0].any() or mask[:, -1].any():
        raise NotMeasurable("the glass runs off the edge of the picture")
    profile = corrected(profile_from_mask(mask, LENS, STANDOFF))
    if abs(profile.max_width - 2 * seen.radius) > AGREEMENT:
        raise NotMeasurable(
            f"{profile.max_width * 1000:.0f} mm wide from the side but {seen.radius * 2000:.0f} mm "
            "from above; another glass is probably in the outline"
        )
    return profile
