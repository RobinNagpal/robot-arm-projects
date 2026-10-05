"""The shared step from mask to report, on masks built by hand.

Only what a solution reads off a report and cannot work out for itself: whether
the picture held the whole glass. The places and widths are covered by every
solution's own tests, since they all come through here.
"""

import numpy as np
from work_cell.glasses.shapes import family

import masks_to_glasses
import render


def _picture() -> render.Picture:
    outline, _ = family("straight_glass", 1, seed=3)[0]
    glass = render.Glass("straight_glass", 0.48, -0.26, outline.height, outline.radius)
    return render.render([glass], render.top_pose())


def test_a_glass_well_inside_the_frame_is_not_cut_off():
    picture = _picture()
    found = masks_to_glasses.one_glass(picture, picture.ids == 1)
    assert found is not None
    assert not found.cut_off


def test_a_mask_running_up_to_the_frame_edge_is_cut_off():
    """One pixel of the glass on the last column is enough, which is the point.

    The question is whether the picture ran out before the glass did, so it is
    answered by the mask reaching the edge and not by how much of it does.
    """
    picture = _picture()
    mask = picture.ids == 1
    top = int(np.nonzero(mask.any(1))[0][0])
    mask[top, -1] = True
    found = masks_to_glasses.one_glass(picture, mask)
    assert found is not None
    assert found.cut_off


def test_a_pixel_the_camera_got_no_reading_for_still_counts_as_reaching_the_edge():
    """The report's own pixels drop it, and the fact about the view keeps it.

    A ray that hit nothing has no point in the room, so it says nothing about
    where the glass stands and the arithmetic leaves it out. It does still say
    the glass ran up against the frame edge, and reading the fact off the usable
    pixels alone would miss exactly the reports it is there to mark.
    """
    taken = _picture()
    depth = taken.depth.copy()
    mask = taken.ids == 1
    top = int(np.nonzero(mask.any(1))[0][0])
    mask[top, 0] = True
    depth[top, 0] = np.inf
    picture = render.Picture(depth, taken.ids, taken.camera_to_world)

    found = masks_to_glasses.one_glass(picture, mask)
    assert found is not None
    assert found.cut_off
    assert not (found.pixels == [top, 0]).all(1).any()
